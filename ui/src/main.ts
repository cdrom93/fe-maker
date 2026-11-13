import { mount } from 'svelte'
import '@fontsource-variable/nunito'
import './app.css'
import App from './App.svelte'
import { watchErrors } from './lib/activity'

watchErrors()

export default mount(App, { target: document.getElementById('app')! })
