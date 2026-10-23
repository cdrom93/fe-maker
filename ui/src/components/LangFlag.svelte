<script lang="ts">
  /** Small flag for the language picker (SVG: flag emoji are not drawn on Windows). */
  let { lang }: { lang: string } = $props()
</script>

<svg class="flag" viewBox="0 0 30 20" width="21" height="14" aria-hidden="true">
  {#if lang === 'fr'}
    <rect width="10" height="20" fill="#002654" /><rect x="10" width="10" height="20" fill="#fff" /><rect x="20" width="10" height="20" fill="#ce1126" />
  {:else if lang === 'it'}
    <rect width="10" height="20" fill="#009246" /><rect x="10" width="10" height="20" fill="#fff" /><rect x="20" width="10" height="20" fill="#ce2b37" />
  {:else if lang === 'es'}
    <rect width="30" height="20" fill="#aa151b" /><rect y="5" width="30" height="10" fill="#f1bf00" />
  {:else if lang === 'en'}
    <!-- United Kingdom -->
    <rect width="30" height="20" fill="#012169" />
    <path d="M0 0 L30 20 M30 0 L0 20" stroke="#fff" stroke-width="4" />
    <path d="M0 0 L30 20 M30 0 L0 20" stroke="#c8102e" stroke-width="1.6" />
    <path d="M15 0 V20 M0 10 H30" stroke="#fff" stroke-width="6" />
    <path d="M15 0 V20 M0 10 H30" stroke="#c8102e" stroke-width="3.4" />
  {/if}
</svg>

<style>
  .flag { display: block; border-radius: 2px; box-shadow: 0 0 0 1px rgb(0 0 0 / 0.25); }
</style>
