import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import FormattedChangeDescription from '@/modules/profile/components/FormattedChangeDescription.vue'

describe('FormattedChangeDescription', () => {
  describe('Plain Text Parsing', () => {
    it('should render plain text without formatting', () => {
      const wrapper = mount(FormattedChangeDescription, {
        props: {
          description: 'This is plain text'
        }
      })

      expect(wrapper.text()).toBe('This is plain text')
    })

    it('should handle text starting with "h" (regression test for infinite loop)', () => {
      const wrapper = mount(FormattedChangeDescription, {
        props: {
          description: 'hello world'
        }
      })

      expect(wrapper.text()).toBe('hello world')
      expect(wrapper.find('span').exists()).toBe(true)
    })

    it('should handle single character "h"', () => {
      const wrapper = mount(FormattedChangeDescription, {
        props: {
          description: 'h'
        }
      })

      expect(wrapper.text()).toBe('h')
    })

    it('should handle multiple "h" characters', () => {
      const wrapper = mount(FormattedChangeDescription, {
        props: {
          description: 'hhhhh'
        }
      })

      expect(wrapper.text()).toBe('hhhhh')
    })

    it('should handle text with many "h" characters scattered throughout', () => {
      const wrapper = mount(FormattedChangeDescription, {
        props: {
          description: 'the happy horse has huge horns'
        }
      })

      expect(wrapper.text()).toBe('the happy horse has huge horns')
    })

    it('should handle empty string', () => {
      const wrapper = mount(FormattedChangeDescription, {
        props: {
          description: ''
        }
      })

      expect(wrapper.text()).toBe('')
    })

    it('should handle whitespace-only string', () => {
      const wrapper = mount(FormattedChangeDescription, {
        props: {
          description: '   '
        }
      })

      // Vue's .text() method normalizes whitespace, so whitespace-only becomes empty
      expect(wrapper.text()).toBe('')
    })
  })

  describe('Code Block Parsing', () => {
    it('should render code blocks with backticks', () => {
      const wrapper = mount(FormattedChangeDescription, {
        props: {
          description: 'Use `const x = 5` in your code'
        }
      })

      expect(wrapper.text()).toContain('Use')
      expect(wrapper.text()).toContain('const x = 5')
      expect(wrapper.text()).toContain('in your code')
      expect(wrapper.find('code').exists()).toBe(true)
      expect(wrapper.find('code').text()).toBe('const x = 5')
    })

    it('should handle multiple code blocks', () => {
      const wrapper = mount(FormattedChangeDescription, {
        props: {
          description: 'Use `var1` and `var2` together'
        }
      })

      const codeElements = wrapper.findAll('code')
      expect(codeElements.length).toBe(2)
      expect(codeElements[0].text()).toBe('var1')
      expect(codeElements[1].text()).toBe('var2')
    })

    it('should handle code block at start of text', () => {
      const wrapper = mount(FormattedChangeDescription, {
        props: {
          description: '`hello` is a greeting'
        }
      })

      expect(wrapper.find('code').text()).toBe('hello')
      expect(wrapper.text()).toContain('is a greeting')
    })
  })

  describe('Bold Text Parsing', () => {
    it('should render bold text with double asterisks', () => {
      const wrapper = mount(FormattedChangeDescription, {
        props: {
          description: 'This is **bold** text'
        }
      })

      expect(wrapper.text()).toContain('This is')
      expect(wrapper.text()).toContain('bold')
      expect(wrapper.text()).toContain('text')
      expect(wrapper.find('strong').exists()).toBe(true)
      expect(wrapper.find('strong').text()).toBe('bold')
    })

    it('should handle multiple bold segments', () => {
      const wrapper = mount(FormattedChangeDescription, {
        props: {
          description: '**First** and **Second** are bold'
        }
      })

      const strongElements = wrapper.findAll('strong')
      expect(strongElements.length).toBe(2)
      expect(strongElements[0].text()).toBe('First')
      expect(strongElements[1].text()).toBe('Second')
    })

    it('should handle bold text at start', () => {
      const wrapper = mount(FormattedChangeDescription, {
        props: {
          description: '**Bold** at the start'
        }
      })

      expect(wrapper.find('strong').text()).toBe('Bold')
      expect(wrapper.text()).toContain('at the start')
    })
  })

  describe('URL Parsing', () => {
    it('should render https URLs as links', () => {
      const wrapper = mount(FormattedChangeDescription, {
        props: {
          description: 'Visit https://example.com for more info'
        }
      })

      const link = wrapper.find('a')
      expect(link.exists()).toBe(true)
      expect(link.text()).toBe('https://example.com')
      expect(link.attributes('href')).toBe('https://example.com')
      expect(link.attributes('target')).toBe('_blank')
    })

    it('should render http URLs as links', () => {
      const wrapper = mount(FormattedChangeDescription, {
        props: {
          description: 'Check http://example.com out'
        }
      })

      const link = wrapper.find('a')
      expect(link.exists()).toBe(true)
      expect(link.text()).toBe('http://example.com')
      expect(link.attributes('href')).toBe('http://example.com')
    })

    it('should handle multiple URLs', () => {
      const wrapper = mount(FormattedChangeDescription, {
        props: {
          description: 'Visit https://site1.com and https://site2.com'
        }
      })

      const links = wrapper.findAll('a')
      expect(links.length).toBe(2)
      expect(links[0].text()).toBe('https://site1.com')
      expect(links[1].text()).toBe('https://site2.com')
    })

    it('should handle URL at start of text', () => {
      const wrapper = mount(FormattedChangeDescription, {
        props: {
          description: 'https://example.com is great'
        }
      })

      const link = wrapper.find('a')
      expect(link.text()).toBe('https://example.com')
      expect(wrapper.text()).toContain('is great')
    })
  })

  describe('Mixed Formatting', () => {
    it('should handle bold, code, and URL together', () => {
      const wrapper = mount(FormattedChangeDescription, {
        props: {
          description: '**Bold** with `code` and https://example.com'
        }
      })

      expect(wrapper.find('strong').text()).toBe('Bold')
      expect(wrapper.find('code').text()).toBe('code')
      expect(wrapper.find('a').text()).toBe('https://example.com')
    })

    it('should handle text with "h" and formatting', () => {
      const wrapper = mount(FormattedChangeDescription, {
        props: {
          description: 'hello **world** and `http` test'
        }
      })

      expect(wrapper.text()).toContain('hello')
      expect(wrapper.find('strong').text()).toBe('world')
      expect(wrapper.find('code').text()).toBe('http')
    })

    it('should handle complex mixed content', () => {
      const wrapper = mount(FormattedChangeDescription, {
        props: {
          description: 'The **happy** horse uses `code` at https://example.com'
        }
      })

      expect(wrapper.text()).toContain('The')
      expect(wrapper.text()).toContain('horse uses')
      expect(wrapper.text()).toContain('at')
      expect(wrapper.find('strong').text()).toBe('happy')
      expect(wrapper.find('code').text()).toBe('code')
      expect(wrapper.find('a').text()).toBe('https://example.com')
    })
  })

  describe('Edge Cases and Regression Tests', () => {
    it('should not hang on text starting with "h" followed by special chars', () => {
      const wrapper = mount(FormattedChangeDescription, {
        props: {
          description: 'h**bold**'
        }
      })

      expect(wrapper.text()).toContain('h')
      expect(wrapper.find('strong').text()).toBe('bold')
    })

    it('should not hang on repeated "h" before special char', () => {
      const wrapper = mount(FormattedChangeDescription, {
        props: {
          description: 'hhhh`code`'
        }
      })

      expect(wrapper.text()).toContain('hhhh')
      expect(wrapper.find('code').text()).toBe('code')
    })

    it('should handle "http" as plain text when not followed by ://', () => {
      const wrapper = mount(FormattedChangeDescription, {
        props: {
          description: 'The word http is not a URL'
        }
      })

      expect(wrapper.text()).toBe('The word http is not a URL')
      expect(wrapper.find('a').exists()).toBe(false)
    })

    it('should handle "https" as plain text when not followed by ://', () => {
      const wrapper = mount(FormattedChangeDescription, {
        props: {
          description: 'The word https is not a URL'
        }
      })

      expect(wrapper.text()).toBe('The word https is not a URL')
      expect(wrapper.find('a').exists()).toBe(false)
    })

    it('should handle very long text with many "h" characters', () => {
      const longText = 'h'.repeat(1000) + ' hello world'
      const wrapper = mount(FormattedChangeDescription, {
        props: {
          description: longText
        }
      })

      expect(wrapper.text()).toContain('hello world')
      expect(wrapper.text().length).toBeGreaterThan(1000)
    })

    it('should handle text with only special characters', () => {
      const wrapper = mount(FormattedChangeDescription, {
        props: {
          description: '**bold** `code`'
        }
      })

      expect(wrapper.find('strong').exists()).toBe(true)
      expect(wrapper.find('code').exists()).toBe(true)
    })

    it('should render all segments in correct order', () => {
      const wrapper = mount(FormattedChangeDescription, {
        props: {
          description: 'Start **bold** middle `code` end https://example.com finish'
        }
      })

      const text = wrapper.text()
      expect(text.indexOf('Start')).toBeLessThan(text.indexOf('bold'))
      expect(text.indexOf('bold')).toBeLessThan(text.indexOf('middle'))
      expect(text.indexOf('middle')).toBeLessThan(text.indexOf('code'))
      expect(text.indexOf('code')).toBeLessThan(text.indexOf('end'))
      expect(text.indexOf('end')).toBeLessThan(text.indexOf('example.com'))
      expect(text.indexOf('example.com')).toBeLessThan(text.indexOf('finish'))
    })
  })

  describe('Component Props', () => {
    it('should accept description prop', () => {
      const wrapper = mount(FormattedChangeDescription, {
        props: {
          description: 'Test description'
        }
      })

      expect(wrapper.props('description')).toBe('Test description')
    })

    it('should update when description prop changes', async () => {
      const wrapper = mount(FormattedChangeDescription, {
        props: {
          description: 'Initial text'
        }
      })

      expect(wrapper.text()).toBe('Initial text')

      await wrapper.setProps({ description: 'Updated text' })

      expect(wrapper.text()).toBe('Updated text')
    })

    it('should handle prop change from plain to formatted', async () => {
      const wrapper = mount(FormattedChangeDescription, {
        props: {
          description: 'plain'
        }
      })

      expect(wrapper.find('strong').exists()).toBe(false)

      await wrapper.setProps({ description: '**bold**' })

      expect(wrapper.find('strong').exists()).toBe(true)
    })
  })
})
