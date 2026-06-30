/* global describe, it, expect */

import { mount } from '@vue/test-utils'
import { NConfigProvider, NDialogProvider, NMessageProvider } from 'naive-ui'

import App from '@/App.vue'

describe('App', () => {
  it('renders Naive UI providers', () => {
    const wrapper = mount(App, {
      global: {
        stubs: {
          RouterView: true,
        },
      },
    })

    expect(wrapper.findComponent(NConfigProvider).exists()).toBe(true)
    expect(wrapper.findComponent(NMessageProvider).exists()).toBe(true)
    expect(wrapper.findComponent(NDialogProvider).exists()).toBe(true)
  })
})
