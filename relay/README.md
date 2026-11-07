# Relais des tickets

Le Worker Cloudflare `fe-maker-tickets` reçoit les tickets envoyés par FE Maker (bouton « Ticket ») et les écrit comme issues du dépôt privé `cdrom93/fe-maker-feedback`. Les testeurs n'ont donc pas besoin de compte GitHub. Le jeton GitHub reste dans le Worker (secret `GITHUB_TOKEN`).

- Les captures et le projet joint (case décochée par défaut) vont dans le dossier `uploads/` du dépôt.
- Chaque ticket reçoit un code secret, gardé par le FE Maker qui l'a envoyé : seul lui relit l'état du ticket et les réponses, et peut répondre.
- Limites : 4 captures de 3 Mo, un projet de 10 Mo, 10 envois par adresse et par tranche de 10 minutes.
- Le jeton doit pouvoir écrire les issues et le contenu de `fe-maker-feedback` (jeton à grain fin : *Issues* et *Contents* en lecture et écriture).

## Déployer

Depuis ce dossier, avec Node.js installé :

```bash
npx wrangler@4 login
npx wrangler@4 deploy
```

La première commande ouvre le navigateur pour se connecter au compte Cloudflare. Le déploiement remplace le code du Worker sans toucher à son secret.

## Tester

```bash
npm test
```

Les tests remplacent GitHub par un faux (`test/relay.test.mjs`).
