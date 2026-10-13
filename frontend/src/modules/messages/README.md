# Messages

Player-to-player messaging: connection requests, blocking, and direct message
threads between accounts. The whole module hides behind the `player_connections`
feature flag (enabled by default), so the nav entry, the route, and every
store action no-op until the flag is on.

## Routes

- `/vault/:id/messages` — MessagesView (flag-gated via route `beforeEnter`)

## Key Files

- `views/MessagesView.vue` — page shell with Conversations / Contacts tabs
- `components/ConversationsPanel.vue` — conversation list + thread, composer, polling
- `components/ThreadView.vue` — message history + composer for one counterpart
- `components/ContactsPanel.vue` — invite form, requests, connections, blocks
- `stores/messages.ts` — contacts, conversations, thread state and transport loop
- `services/messagesService.ts` — connections/blocks/messages API calls
- `models/messages.ts` — hand-written wire types (no types:generate)

## Conversations, requests, and the composer

The Conversations tab lists every thread (with unread counts and last-message
previews) and a separate Message Requests section for first messages from
non-connections; accepting one promotes the sender to a connection via
`POST /messages/{user_id}/accept`. Opening a row fetches the thread and shows
the composer; Enter sends, Shift+Enter inserts a newline.

## Live updates are polling

There is no personal WebSocket endpoint for direct messages on the backend (the
only WS route is dweller chat; notifications use SSE). The open thread is
polled on a ~5s interval and the conversation list refreshes on mount and
window focus. The polling lives **inside** `stores/messages.ts` — components
only call `openThread()` / `closeThread()` / `loadConversations()`, so a future
WebSocket/SSE push can replace the transport without touching any component.

_Backend follow-up: a per-user live push channel for direct messages._
