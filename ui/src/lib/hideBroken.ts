// Hides an <img> while its picture cannot be loaded, and shows it again when its src changes to one that can.
export function hideBroken(img: HTMLImageElement) {
  const hide = () => (img.style.visibility = 'hidden')
  const show = () => (img.style.visibility = '')
  img.addEventListener('error', hide)
  img.addEventListener('load', show)
  return { destroy() { img.removeEventListener('error', hide); img.removeEventListener('load', show) } }
}
