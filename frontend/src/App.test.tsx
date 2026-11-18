import { cleanup, render, screen, within } from '@testing-library/react'
import { afterEach, expect, it } from 'vitest'
import App from './App'

afterEach(cleanup)

it('introduces Rostaroo and makes its development status visible', () => {
  render(<App />)

  expect(within(screen.getByRole('banner')).getByText(/^Rostaroo/)).toBeTruthy()

  const main = within(screen.getByRole('main'))
  expect(
    main.getByRole('heading', {
      level: 1,
      name: 'Staff rostering for Australian hospitality',
    }),
  ).toBeTruthy()
  expect(main.getByText('In development')).toBeTruthy()
  expect(main.getByText(/plan weekly rosters/)).toBeTruthy()
})
