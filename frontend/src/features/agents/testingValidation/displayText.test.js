import { describe, expect, it } from 'vitest'

import { sanitizeDisplayText } from './displayText.js'

describe('sanitizeDisplayText', () => {
  it('leaves clean and legitimate Unicode text unchanged', () => {
    expect(sanitizeDisplayText('Crème brûlée — API → UI')).toBe('Crème brûlée — API → UI')
  })

  it.each([
    ['â€œThe user shall create a booking.â€', '"The user shall create a booking."'],
    ['â€�Validation failedâ€�', '"Validation failed"'],
    ['Agentâ€™s interpretation and â€˜reviewâ€™', "Agent's interpretation and 'review'"],
    ['requirements.txt Â· Accepted', 'requirements.txt | Accepted'],
    ['Requirement â†’ Supported By â†’ Endpoint', 'Requirement | Supported By | Endpoint'],
    ['retry â€“ available', 'retry - available'],
    ['oneâ€”two', 'one-two'],
    ['Loadingâ€¦', 'Loading...'],
    ['Ready Â | Complete', 'Ready | Complete'],
  ])('repairs known mojibake in %j', (input, expected) => {
    expect(sanitizeDisplayText(input)).toBe(expected)
  })
})
