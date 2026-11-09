/** A new project's folder inside the folder chosen in the picker: named after the project, without the characters
 * Windows refuses in a file name. */
export function inFolder(parent: string, name: string): string {
  const folder = name.trim().replace(/[<>:"/\\|?*]+/g, '').replace(/[. ]+$/, '') || 'project'
  return `${parent.replace(/[\\/]+$/, '')}\\${folder}`
}
