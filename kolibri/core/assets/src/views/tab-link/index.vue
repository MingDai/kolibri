<template>

  <li>
    <router-link :to="link" class="tab" :class="{ 'tab-has-icon-and-title': type === 'icon-and-title' }">

      <div v-if="type === 'icon' || type === 'icon-and-title'" class="tab-icon">
        <ui-icon :icon="icon" :ariaLabel="title" class="icon"/>
      </div>

      <div v-if="type === 'title' || type === 'icon-and-title'" class="tab-title">
        {{ title }}
      </div>
    </router-link>
  </li>

</template>


<script>

  const ValidateLinkObject = require('kolibri.utils.validateLinkObject');

  module.exports = {
    props: {
      type: {
        type: String,
        validator(type) {
          return ['title', 'icon', 'icon-and-title'].includes(type);
        },
        required: true,
      },
      title: {
        type: String,
        required: false,
      },
      icon: {
        type: String,
        required: false,
      },
      link: {
        type: Object,
        required: true,
        validator: ValidateLinkObject,
      },
    },
    components: {
      'ui-icon': require('keen-ui/src/UiIcon'),
    },
  };

</script>


<style lang="stylus" scoped>

  @require '../tab-items.styl'

</style>
