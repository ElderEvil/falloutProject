import { describe, it, expect } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import FormattedChangeDescription from '@/modules/profile/components/FormattedChangeDescription.vue'

const render = (description: string) =>
  mount(FormattedChangeDescription, { props: { description } })

describe('FormattedChangeDescription', () => {
  describe('plain text', () => {
    it.each([
      ['plain text without formatting', 'This is plain text', 'This is plain text'],
      ['text starting with "h" (regression test for infinite loop)', 'hello world', 'hello world'],
      ['a single character "h"', 'h', 'h'],
      ['multiple "h" characters', 'hhhhh', 'hhhhh'],
      [
        'text with many "h" characters scattered throughout',
        'the happy horse has huge horns',
        'the happy horse has huge horns',
      ],
      ['an empty string', '', ''],
      ['a whitespace-only string', '   ', ''],
    ])('renders %s verbatim', (_label, description, expected) => {
      expect(render(description).text()).toBe(expected)
    })

    it('wraps plain text in a span', () => {
      expect(render('hello world').find('span').exists()).toBe(true)
    })
  })

  describe('code blocks', () => {
    it('renders a code block with backticks alongside its prose', () => {
      const wrapper = render('Use `const x = 5` in your code')

      expect(wrapper.text()).toContain('Use')
      expect(wrapper.text()).toContain('const x = 5')
      expect(wrapper.text()).toContain('in your code')
      expect(wrapper.find('code').exists()).toBe(true)
      expect(wrapper.find('code').text()).toBe('const x = 5')
    })

    it('renders each backticked segment as its own code block', () => {
      const codeElements = render('Use `var1` and `var2` together').findAll('code')

      expect(codeElements.map((element) => element.text())).toEqual(['var1', 'var2'])
    })

    it('renders a code block at the start of the text', () => {
      const wrapper = render('`hello` is a greeting')

      expect(wrapper.find('code').text()).toBe('hello')
      expect(wrapper.text()).toContain('is a greeting')
    })
  })

  describe('bold text', () => {
    it('renders bold text with double asterisks alongside its prose', () => {
      const wrapper = render('This is **bold** text')

      expect(wrapper.text()).toContain('This is')
      expect(wrapper.text()).toContain('bold')
      expect(wrapper.text()).toContain('text')
      expect(wrapper.find('strong').exists()).toBe(true)
      expect(wrapper.find('strong').text()).toBe('bold')
    })

    it('renders each bold segment as its own strong element', () => {
      const strongElements = render('**First** and **Second** are bold').findAll('strong')

      expect(strongElements.map((element) => element.text())).toEqual(['First', 'Second'])
    })

    it('renders bold text at the start of the text', () => {
      const wrapper = render('**Bold** at the start')

      expect(wrapper.find('strong').text()).toBe('Bold')
      expect(wrapper.text()).toContain('at the start')
    })
  })

  describe('URL parsing', () => {
    it.each([
      ['https', 'Visit https://example.com for more info'],
      ['http', 'Check http://example.com out'],
    ])('renders %s URLs as links', (scheme, description) => {
      const link = render(description).find('a')

      expect(link.exists()).toBe(true)
      expect(link.text()).toBe(`${scheme}://example.com`)
      expect(link.attributes('href')).toBe(`${scheme}://example.com`)
    })

    it('opens links in a new tab', () => {
      expect(render('Visit https://example.com for more info').find('a').attributes('target')).toBe(
        '_blank'
      )
    })

    it('renders each URL as its own link', () => {
      const links = render('Visit https://site1.com and https://site2.com').findAll('a')

      expect(links.map((link) => link.text())).toEqual(['https://site1.com', 'https://site2.com'])
    })

    it('renders a URL at the start of the text', () => {
      const wrapper = render('https://example.com is great')

      expect(wrapper.find('a').text()).toBe('https://example.com')
      expect(wrapper.text()).toContain('is great')
    })
  })

  describe('mixed formatting', () => {
    it('renders bold, code and a URL together', () => {
      const wrapper = render('**Bold** with `code` and https://example.com')

      expect(wrapper.find('strong').text()).toBe('Bold')
      expect(wrapper.find('code').text()).toBe('code')
      expect(wrapper.find('a').text()).toBe('https://example.com')
    })

    it('renders bold and code next to text containing "h"', () => {
      const wrapper = render('hello **world** and `http` test')

      expect(wrapper.text()).toContain('hello')
      expect(wrapper.find('strong').text()).toBe('world')
      expect(wrapper.find('code').text()).toBe('http')
    })

    it('renders complex mixed content in prose order', () => {
      const wrapper = render('The **happy** horse uses `code` at https://example.com')

      expect(wrapper.text()).toContain('The')
      expect(wrapper.text()).toContain('horse uses')
      expect(wrapper.text()).toContain('at')
      expect(wrapper.find('strong').text()).toBe('happy')
      expect(wrapper.find('code').text()).toBe('code')
      expect(wrapper.find('a').text()).toBe('https://example.com')
    })
  })

  describe('edge cases and regressions', () => {
    it.each([
      {
        label: 'bold markers after a leading "h"',
        description: 'h**bold**',
        prose: 'h',
        selector: 'strong',
        segment: 'bold',
      },
      {
        label: 'a code block after repeated "h"',
        description: 'hhhh`code`',
        prose: 'hhhh',
        selector: 'code',
        segment: 'code',
      },
    ])('does not hang on $label', ({ description, prose, selector, segment }) => {
      const wrapper = render(description)

      expect(wrapper.text()).toContain(prose)
      expect(wrapper.find(selector).text()).toBe(segment)
    })

    it.each(['The word http is not a URL', 'The word https is not a URL', 'check http out'])(
      'renders %s as plain text',
      (description) => {
        const wrapper = render(description)

        expect(wrapper.text()).toBe(description)
        expect(wrapper.find('a').exists()).toBe(false)
      }
    )

    it('handles very long text with many "h" characters', () => {
      const wrapper = render('h'.repeat(1000) + ' hello world')

      expect(wrapper.text()).toContain('hello world')
      expect(wrapper.text().length).toBeGreaterThan(1000)
    })

    it('handles text made only of special characters', () => {
      const wrapper = render('**bold** `code`')

      expect(wrapper.find('strong').exists()).toBe(true)
      expect(wrapper.find('code').exists()).toBe(true)
    })

    it('renders all segments in the correct order', () => {
      const text = render('Start **bold** middle `code` end https://example.com finish').text()

      expect(text.indexOf('Start')).toBeLessThan(text.indexOf('bold'))
      expect(text.indexOf('bold')).toBeLessThan(text.indexOf('middle'))
      expect(text.indexOf('middle')).toBeLessThan(text.indexOf('code'))
      expect(text.indexOf('code')).toBeLessThan(text.indexOf('end'))
      expect(text.indexOf('end')).toBeLessThan(text.indexOf('example.com'))
      expect(text.indexOf('example.com')).toBeLessThan(text.indexOf('finish'))
    })
  })

  describe('malformed input regressions', () => {
    it.each([
      ['a lone backtick', '`'],
      ['a lone backtick mid-text', 'text ` unclosed more text'],
      ['a single asterisk', '*'],
      ['a lone backtick next to a single asterisk', '` and * in text'],
    ])('renders %s literally without hanging', (_label, description) => {
      expect(render(description).text()).toBe(description)
    })

    it.each(['**unclosed', '***test'])(
      'renders %s literally without a strong element',
      (description) => {
        const wrapper = render(description)

        expect(wrapper.text()).toBe(description)
        expect(wrapper.find('strong').exists()).toBe(false)
      }
    )

    it('renders a backtick-wrapped URL as code, not a link', () => {
      const wrapper = render('`https://example.com`')

      expect(wrapper.find('code').exists()).toBe(true)
      expect(wrapper.find('code').text()).toBe('https://example.com')
      expect(wrapper.find('a').exists()).toBe(false)
    })
  })

  describe('component props', () => {
    it('accepts the description prop', () => {
      expect(render('Test description').props('description')).toBe('Test description')
    })

    it('re-renders when the description prop changes', async () => {
      const wrapper = render('Initial text')

      expect(wrapper.text()).toBe('Initial text')

      await wrapper.setProps({ description: 'Updated text' })

      expect(wrapper.text()).toBe('Updated text')
    })

    it('re-renders when the description goes from plain to formatted', async () => {
      const wrapper = render('plain')

      expect(wrapper.find('strong').exists()).toBe(false)

      await wrapper.setProps({ description: '**bold**' })

      expect(wrapper.find('strong').exists()).toBe(true)
    })
  })
})
