# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Un seul utilisateur réel : le propriétaire du projet. L'app est son gestionnaire
de tâches personnel, utilisé au quotidien, en visites courtes et répétées.

L'authentification par e-mail et la politique RLS par utilisateur (`supabase/schema.sql`)
existent pour isoler et synchroniser ses données entre appareils, pas pour servir
une base d'utilisateurs. Aucun autre public n'est confirmé : ni proches, ni
inscription publique, ni usage en vitrine. Le travail futur ne doit pas inventer
de second public ni concevoir pour un primo-visiteur inconnu.

## Product Purpose

Capturer une tâche et la terminer avec le moins de friction possible.

La réussite est mesurée en vitesse d'usage quotidien : le temps entre « j'y pense »
et « c'est noté », puis entre « c'est fait » et « c'est coché ». Un clic, un champ
ou un écran en trop est un échec, même s'il est joli. Le code et l'architecture
sont des moyens, pas la finalité ; l'impression visuelle non plus.

## Positioning

Aucune revendication concurrentielle n'est établie, et il ne faut pas en fabriquer
une. Ce n'est pas un produit sur un marché : sa seule différence défendable est
l'ajustement exact au flux de travail d'une personne. Les décisions se tranchent
par « est-ce plus rapide pour lui ? », jamais par « est-ce que ça nous distingue
de la concurrence ? ».

## Operating Context

- Usage quotidien, par sessions brèves, entrecoupées. L'app est rouverte souvent,
  rarement contemplée.
- Interface responsive conçue mobile-first (`docs/superpowers/specs/2026-07-12-todo-app-design.md`),
  donc un usage sur petit écran est prévu par l'implémentation.
- Thème clair et sombre, choix persisté dans `localStorage`.
- **Indécis :** la répartition réelle entre mobile et bureau, et le moment de la
  journée où l'app est le plus utilisée, ne sont pas établis. À confirmer avant
  toute optimisation qui favoriserait un contexte au détriment de l'autre.

## Capabilities and Constraints

Fonctionnalités confirmées (présentes dans le code) :

- Authentification e-mail / mot de passe via Supabase ; isolation des données par
  politique RLS.
- CRUD des tâches, bascule « terminé ».
- Priorité (`basse` / `moyenne` / `haute`) et date d'échéance optionnelle.
- Filtres : toutes / à faire / terminées.
- Réorganisation manuelle par glisser-déposer, persistée via la colonne `position`.
- Thème clair/sombre, retours par toasts.

Contraintes techniques actuelles :

- SPA Vite, une seule page, aucun routeur côté client.
- Les composants n'appellent jamais Supabase directement : seuls `src/hooks/` et
  `src/lib/taskApi.ts` le font.
- Tout le texte visible vit dans `src/copy/strings.ts`.
- Chaque livraison passe `npm test` et `npm run build`.

**Indécis — à ne pas traiter comme des engagements durables :** le caractère
définitif de la page unique sans routeur, de la centralisation du texte dans
`strings.ts`, et du périmètre v1 (pas de tags, partage, recherche, ni notifications
d'échéance). Ce sont les choix de l'implémentation actuelle, décrits dans
`docs/superpowers/specs/2026-07-12-todo-app-design.md` ; ils n'ont pas été confirmés
comme intangibles. Demander avant de s'appuyer sur eux pour refuser une évolution.

## Brand Commitments

- **Langue et registre : contraignants.** Français, tutoiement. La voix est
  chaleureuse, directe, encourageante — jamais corporate, jamais sèche.
  `src/copy/strings.ts` est la référence vivante de ce ton (« Tout est fait ! Tu
  gères. », « Rien à faire pour l'instant. Profites-en. »). Toute nouvelle chaîne
  doit pouvoir s'asseoir à côté des existantes sans détonner.
- **Indécis :** il n'y a pas de nom de marque confirmé. « To-Do App » et `todo-app`
  sont des libellés techniques, pas une identité ; aucun logo ni actif de marque
  n'existe. Ne pas inventer de nom, de baseline ni de logo sans demander.

## Evidence on Hand

- `docs/superpowers/specs/2026-07-12-todo-app-design.md` — spécification de
  conception approuvée (stack, architecture, périmètre v1 et hors-scope).
- `docs/superpowers/plans/2026-07-12-todo-app.md` — plan d'implémentation.
- `src/copy/strings.ts` — l'intégralité du texte produit ; référence de la voix.
- `supabase/schema.sql` — modèle de données et politique RLS réels.

**Absences à ne jamais combler par de l'invention :** aucun utilisateur tiers,
aucun témoignage, aucune métrique d'usage, aucun chiffre de performance mesuré,
aucune mention presse, aucune donnée de démonstration. Si une surface a besoin de
contenu d'exemple, il doit être étiqueté comme tel.

## Product Principles

1. **La capture doit coûter moins cher qu'un post-it.** Toute étape ajoutée entre
   l'intention et la tâche enregistrée doit se justifier par un gain mesurable.
2. **Un seul utilisateur réel.** Pas de surface sociale, pas de pédagogie
   d'onboarding pour inconnu, pas de réassurance destinée à convaincre.
3. **L'authentification est un sas, pas une destination.** Elle doit s'effacer :
   la liste est le produit.
4. **La voix tutoie et encourage.** Contrainte de marque, pas une préférence de
   rédaction.
5. **Une fonctionnalité se paie en vitesse quotidienne.** Ce qui enrichit le
   produit sans accélérer l'usage est un coût, pas un gain.
