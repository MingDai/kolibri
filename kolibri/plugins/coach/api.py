import datetime

from dateutil.parser import parse
from django.db.models import Min, Q
from django.utils import timezone
from kolibri.auth.constants import role_kinds
from kolibri.auth.models import Collection, FacilityUser
from kolibri.content.content_db_router import default_database_is_attached, get_active_content_database
from kolibri.content.models import ContentNode
from kolibri.logger.models import ContentSummaryLog, MasteryLog
from rest_framework import pagination, permissions, viewsets

from .serializers import ContentReportSerializer, ContentSummarySerializer, UserReportSerializer
from .utils.return_users import get_members_or_user


class OptionalPageNumberPagination(pagination.PageNumberPagination):
    """
    Pagination class that allows for page number-style pagination, when requested.
    To activate, the `page_size` argument must be set. For example, to request the first 20 records:
    `?page_size=20&page=1`
    """
    page_size = None
    page_size_query_param = "page_size"


class KolibriReportPermissions(permissions.BasePermission):

    # check if requesting user has permission for collection or user
    def has_permission(self, request, view):
        collection_kind = view.kwargs.get('collection_kind', 'user')
        collection_or_user_pk = view.kwargs.get('collection_id', view.kwargs.get('pk'))

        allowed_roles = [role_kinds.ADMIN, role_kinds.COACH]
        if 'user' == collection_kind:
            return request.user.has_role_for(allowed_roles, FacilityUser.objects.get(pk=collection_or_user_pk))
        else:
            return request.user.has_role_for(allowed_roles, Collection.objects.get(pk=collection_or_user_pk))


class UserReportViewSet(viewsets.ModelViewSet):

    permission_classes = (KolibriReportPermissions,)
    pagination_class = OptionalPageNumberPagination
    serializer_class = UserReportSerializer

    def get_queryset(self):
        assert 'user' != self.kwargs['collection_kind'], 'only a `collection` should be passed to this endpoint'
        return get_members_or_user(self.kwargs['collection_kind'], self.kwargs['collection_id'])


class ContentReportViewSet(viewsets.ModelViewSet):

    permission_classes = (KolibriReportPermissions,)
    pagination_class = OptionalPageNumberPagination
    serializer_class = ContentReportSerializer

    def get_queryset(self):
        content_node_id = self.kwargs['content_node_id']
        return ContentNode.objects.filter(parent=content_node_id).order_by('lft')


class ContentSummaryViewSet(viewsets.ModelViewSet):

    permission_classes = (KolibriReportPermissions,)
    serializer_class = ContentSummarySerializer

    def get_queryset(self):
        return ContentNode.objects.all().order_by('lft')


class UserSummaryViewSet(viewsets.ModelViewSet):

    permission_classes = (KolibriReportPermissions,)
    serializer_class = UserReportSerializer

    def get_queryset(self):
        return FacilityUser.objects.all()


class RecentReportViewSet(viewsets.ModelViewSet):

    permission_classes = (KolibriReportPermissions,)
    pagination_class = OptionalPageNumberPagination
    serializer_class = ContentReportSerializer

    def get_queryset(self):
        attempted_mastery_logs = MasteryLog.objects.filter(attemptlogs__isnull=False)
        query_node = ContentNode.objects.get(pk=self.kwargs['content_node_id'])
        if self.request.query_params.get('last_active_time'):
            # Last active time specified
            datetime_cutoff = parse(self.request.query_params.get('last_active_time'))
        else:
            datetime_cutoff = timezone.now() - datetime.timedelta(7)
        # Set on the kwargs to pass into the serializer
        self.kwargs['last_active_time'] = datetime_cutoff.isoformat()
        if default_database_is_attached():  # if possible, do a direct join between the content and default databases
            channel_alias = get_active_content_database()
            SummaryLogManager = ContentSummaryLog.objects.using(channel_alias)
        else:
            SummaryLogManager = ContentSummaryLog.objects
        recent_content_items = SummaryLogManager.filter_by_topic(query_node).filter(
            Q(progress__gt=0) | Q(masterylogs__in=attempted_mastery_logs),
            user__in=list(get_members_or_user(self.kwargs['collection_kind'], self.kwargs['collection_id'])),
            end_timestamp__gte=datetime_cutoff).values_list('content_id', flat=True)
        if not default_database_is_attached():
            recent_content_items = list(recent_content_items)
        # note from rtibbles:
        # As good as either I or jamalex could come up with to ensure that we only return
        # unique content_id'ed ContentNodes from the coach recent report endpoint.
        # Would have loved to use distinct('content_id'), but unfortunately DISTINCT ON is Postgresql only
        pks_with_unique_content_ids = ContentNode.objects.filter(
            content_id__in=recent_content_items).values('content_id').order_by('lft').annotate(
            pk=Min('pk')).values_list('pk', flat=True)
        return ContentNode.objects.filter(pk__in=pks_with_unique_content_ids).order_by('lft')
