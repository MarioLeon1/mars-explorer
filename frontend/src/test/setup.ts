// Adds jest-dom matchers (toBeInTheDocument, ...). With `globals: true`, Testing Library
// unmounts rendered trees after each test automatically.
import '@testing-library/jest-dom/vitest'

// jsdom does not implement layout APIs; stub the ones our components call.
if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = function scrollIntoView() {}
}
