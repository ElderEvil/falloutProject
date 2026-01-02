# Messaging & Notification Architecture - Design Options

## Current State Analysis

### Existing: LLMInteraction Model
**Location**: `backend/app/models/llm_interaction.py`

**Current Purpose**: Statistics tracking for AI interactions
- Stores: `parameters`, `response`, `usage`
- Links: `prompt_id`, `user_id`
- **Intentionally not stored on frontend** (just for stats)

**Existing Chat System**:
- Frontend: `DwellerChatPage.vue` - User ↔ Dweller conversations
- Uses PydanticAI for real-time conversations
- History visible in UI but not persisted to database per message
- LLMInteraction tracks the AI calls, not the conversation flow

---

## Problem Statement

We need multiple communication/notification systems:

1. **User ↔ Dweller Chat** (Already exists, working)
   - Interactive two-way conversations
   - Real-time AI responses
   - Example: "How are you?" → Dweller responds

2. **Dweller → User Notifications** (NEW, what we want)
   - One-way alerts about game events
   - Example: "I found a weapon in the wasteland!"
   - Should be **persistent** and **reviewable**

3. **Dweller ↔ Dweller Social** (Future feature)
   - Dwellers talk to each other
   - Player can observe but not participate
   - Example: Sarah tells John about her day

4. **System → User Notifications** (NEW, what we want)
   - Game state alerts
   - Example: "Low power! Build more generators!"

---

## Architecture Options

### Option 1: Three Separate Models (Clean Separation)

```
┌─────────────────────────────────────────────────────────────┐
│                     LLMInteraction                          │
│  (Statistics only - existing, no changes needed)            │
│  - prompt_id, user_id, parameters, response, usage          │
│  - Purpose: Track AI API usage and costs                    │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                      ChatMessage                            │
│  (New model for persistent chat history)                    │
│  - chat_id (FK to Chat)                                     │
│  - from_user_id | from_dweller_id (one must be null)        │
│  - message_text                                             │
│  - created_at                                               │
│  - llm_interaction_id (optional, for linking to stats)      │
└─────────────────────────────────────────────────────────────┘
         ↑
         │ belongs to
         │
┌─────────────────────────────────────────────────────────────┐
│                         Chat                                │
│  (New model - conversation container)                       │
│  - participant_1_id (user_id OR dweller_id)                 │
│  - participant_1_type (enum: user, dweller)                 │
│  - participant_2_id (user_id OR dweller_id)                 │
│  - participant_2_type (enum: user, dweller)                 │
│  - vault_id                                                 │
│  - last_message_at                                          │
│  - is_active                                                │
│                                                             │
│  Supports:                                                  │
│  - User ↔ Dweller (participant_1_type=user, p2=dweller)     │
│  - Dweller ↔ Dweller (both participant types = dweller)     │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    Notification                             │
│  (One-way alerts to users only)                             │
│  - user_id (FK) - always a user, never dweller              │
│  - vault_id (optional)                                      │
│  - from_dweller_id (optional - null for system messages)    │
│  - notification_type (enum)                                 │
│  - title, message                                           │
│  - priority, is_read, is_dismissed                          │
│  - metadata (JSON - context data)                           │
│  - created_at, read_at                                      │
│                                                             │
│  Purpose: Game event notifications                          │
│  Examples:                                                  │
│  - "Sarah found a weapon!" (from_dweller_id = Sarah)        │
│  - "Low power!" (from_dweller_id = null, system)            │
│  - "Training complete!" (from_dweller_id = John)            │
└─────────────────────────────────────────────────────────────┘
```

**Pros**:
- ✅ Clean separation of concerns
- ✅ Chat supports future dweller-to-dweller conversations
- ✅ Notifications stay simple and focused
- ✅ LLMInteraction unchanged (no breaking changes)
- ✅ Each model has one clear purpose

**Cons**:
- ❌ More models to maintain (3 new tables)
- ❌ More complex to implement initially

---

### Option 2: Two Models - Extend LLMInteraction (Reuse Existing)

```
┌─────────────────────────────────────────────────────────────┐
│                  LLMInteraction (Extended)                  │
│  - prompt_id, user_id                                       │
│  - parameters, response, usage (existing fields)            │
│  - from_dweller_id (NEW - optional)                         │
│  - to_dweller_id (NEW - optional)                           │
│  - message_text (NEW - the actual message)                  │
│  - interaction_type (NEW - enum: chat, notification)        │
│  - is_read (NEW - for notifications)                        │
│                                                             │
│  Dual purpose:                                              │
│  1. Statistics (original) - when interaction_type = stats   │
│  2. Chat messages - when interaction_type = chat            │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                      Notification                           │
│  (Same as Option 1 - focused on user alerts)                │
└─────────────────────────────────────────────────────────────┘
```

**Pros**:
- ✅ Reuses existing table
- ✅ Fewer new models
- ✅ Chat messages automatically linked to AI usage stats

**Cons**:
- ❌ LLMInteraction becomes bloated (too many purposes)
- ❌ Mixing statistics with user-facing messages
- ❌ Hard to query (need filters everywhere)
- ❌ Breaking change to existing model
- ❌ Confusing purpose: "Is this for stats or messages?"

---

### Option 3: Two Models - Chat + Notification (Recommended ⭐)

```
┌─────────────────────────────────────────────────────────────┐
│                     LLMInteraction                          │
│  (Unchanged - keep for statistics only)                     │
│  - Just track AI usage and costs                            │
│  - Can optionally reference ChatMessage via new field        │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                      ChatMessage                            │
│  (New - persistent conversation history)                    │
│  - id (UUID)                                                │
│  - vault_id (FK) - which vault this belongs to              │
│  - from_user_id (optional FK to User)                       │
│  - from_dweller_id (optional FK to Dweller)                 │
│  - to_user_id (optional FK to User)                         │
│  - to_dweller_id (optional FK to Dweller)                   │
│  - message_text (string, max 2000 chars)                    │
│  - created_at (timestamp)                                   │
│  - llm_interaction_id (optional FK - link to AI stats)      │
│                                                             │
│  Flexibility:                                               │
│  - User → Dweller: from_user_id + to_dweller_id             │
│  - Dweller → User: from_dweller_id + to_user_id             │
│  - Dweller → Dweller: from_dweller_id + to_dweller_id       │
│                                                             │
│  Simple queries:                                            │
│  - Get conversation: WHERE (from_user=X AND to_dweller=Y)   │
│                      OR (from_dweller=Y AND to_user=X)      │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    Notification                             │
│  (One-way alerts - user only)                               │
│  - user_id (always to a user)                               │
│  - from_dweller_id (optional)                               │
│  - notification_type, priority                              │
│  - title, message                                           │
│  - is_read, is_dismissed                                    │
│  - metadata (JSON)                                          │
│  - created_at, read_at                                      │
└─────────────────────────────────────────────────────────────┘
```

**Pros**:
- ✅ Clean separation: ChatMessage for conversations, Notification for alerts
- ✅ LLMInteraction stays focused on statistics
- ✅ ChatMessage simple and flexible (no Chat container needed)
- ✅ Easy to query and understand
- ✅ Future-proof for dweller-to-dweller conversations
- ✅ No breaking changes to existing code

**Cons**:
- ❌ Need to query both directions for full conversation
  - Solution: Create a view or helper function

---

## Comparison Table

| Feature | Option 1 (3 Models) | Option 2 (Extend LLM) | Option 3 (2 Models) ⭐ |
|---------|--------------------|-----------------------|----------------------|
| Separation of concerns | Excellent | Poor | Excellent |
| Query simplicity | Good | Poor | Good |
| Future dweller-dweller chat | Yes (Chat model) | Yes but complex | Yes (ChatMessage) |
| Breaking changes | None | Major | None |
| Number of new tables | 3 | 0 | 2 |
| Complexity | Medium | Low | Low-Medium |
| Maintainability | High | Low | High |
| **Recommendation** | 🟡 Good | 🔴 No | 🟢 **Best** |

---

## Recommended Approach: Option 3

### Why Option 3?

1. **Clear Separation**:
   - `LLMInteraction` → AI usage statistics (unchanged)
   - `ChatMessage` → Persistent conversations (user ↔ dweller, dweller ↔ dweller)
   - `Notification` → One-way game alerts (exploration, combat, training, etc.)

2. **Simple Mental Model**:
   - Want to chat with dweller? → `ChatMessage`
   - Want to see game alerts? → `Notification`
   - Want to track AI costs? → `LLMInteraction`

3. **No Breaking Changes**:
   - Existing code continues to work
   - LLMInteraction stays as-is
   - Current chat UI just needs to save messages to `ChatMessage`

4. **Future-Proof**:
   - Dweller-to-dweller conversations: Just use `from_dweller_id + to_dweller_id`
   - Group chats: Can extend with `chat_room_id` later if needed

---

## Implementation Plan for Option 3

### Phase 1: Create Models (1-2 hours)

#### ChatMessage Model
```python
class ChatMessage(BaseUUIDModel, table=True):
    vault_id: UUID = Field(foreign_key="vault.id", index=True)

    # Source (one must be set)
    from_user_id: UUID | None = Field(default=None, foreign_key="user.id", index=True)
    from_dweller_id: UUID | None = Field(default=None, foreign_key="dweller.id", index=True)

    # Destination (one must be set)
    to_user_id: UUID | None = Field(default=None, foreign_key="user.id", index=True)
    to_dweller_id: UUID | None = Field(default=None, foreign_key="dweller.id", index=True)

    message_text: str = Field(max_length=2000)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)

    # Optional: Link to LLMInteraction for AI-generated messages
    llm_interaction_id: UUID | None = Field(default=None, foreign_key="llminteraction.id")

    # Relationships
    from_user: "User | None" = Relationship(...)
    from_dweller: "Dweller | None" = Relationship(...)
    to_user: "User | None" = Relationship(...)
    to_dweller: "Dweller | None" = Relationship(...)
```

#### Notification Model
```python
# Already created! Just needs migration
```

### Phase 2: Migration
```bash
alembic revision --autogenerate -m "Add ChatMessage and Notification models"
alembic upgrade head
```

### Phase 3: CRUD Operations
- `chat_message.py` - get_conversation(), create_message()
- `notification.py` - Already created!

### Phase 4: Update Existing Chat Endpoint (1-2 hours)
**File**: `backend/app/api/v1/endpoints/chat.py`

Add after AI response:
```python
# Save to ChatMessage for history
await chat_message_crud.create(
    db,
    obj_in=ChatMessageCreate(
        vault_id=dweller.vault_id,
        from_user_id=current_user.id,
        to_dweller_id=dweller.id,
        message_text=user_message,
        llm_interaction_id=llm_interaction.id  # Link to stats
    )
)

# Save AI response
await chat_message_crud.create(
    db,
    obj_in=ChatMessageCreate(
        vault_id=dweller.vault_id,
        from_dweller_id=dweller.id,
        to_user_id=current_user.id,
        message_text=ai_response,
        llm_interaction_id=llm_interaction.id  # Same interaction
    )
)
```

### Phase 5: WebSocket Infrastructure (2-3 hours)
- `ConnectionManager` - Already created!
- WebSocket endpoint - Already created!
- Notification REST API - Already created!

### Phase 6: Frontend (3-4 hours)
- WebSocket composable
- Notification store
- ChatMessage store (for history)
- UI components

---

## Data Flow Examples

### Example 1: User Chats with Dweller
```
User: "How are you?"
  ↓
1. POST /api/v1/chat/dweller/{dweller_id}
2. Create ChatMessage (from_user → to_dweller, text="How are you?")
3. Call PydanticAI
4. Create LLMInteraction (for statistics)
5. Create ChatMessage (from_dweller → to_user, text="I'm doing great!", llm_interaction_id=X)
6. Return response to user
```

### Example 2: Dweller Finds Item in Wasteland
```
Game Loop detects: Sarah found weapon
  ↓
1. NotificationService.notify_exploration_item_found()
2. Create Notification (from_dweller_id=Sarah, user_id=player, type=EXPLORATION_UPDATE)
3. Send via WebSocket to player immediately
4. Player sees toast: "Sarah found a weapon!"
5. Notification saved in database (reviewable later)
```

### Example 3: Dwellers Chat With Each Other (Future)
```
Game Loop: Sarah and John are friends in same room
  ↓
1. Generate conversation between them (AI)
2. Create ChatMessage (from_dweller_id=Sarah, to_dweller_id=John, text="Hey John!")
3. Create ChatMessage (from_dweller_id=John, to_dweller_id=Sarah, text="Hi Sarah!")
4. Optional: Send Notification to user: "Sarah and John are chatting!"
5. User can view conversation in relationship panel
```

---

## Migration Path from Current State

### What Already Exists ✅
- LLMInteraction model (keep as-is)
- Chat UI (`DwellerChatPage.vue`)
- PydanticAI integration
- WebSocket infrastructure (just created)
- Notification model (just created)

### What Needs to Be Added ➕
1. **ChatMessage model** - New table
2. **Update chat endpoint** - Save messages to ChatMessage
3. **Frontend chat history** - Display old messages from ChatMessage
4. **Notification integration** - Connect game events to NotificationService

### What Doesn't Change ✨
- LLMInteraction (no breaking changes)
- Existing chat UI structure
- PydanticAI logic
- All other models

---

## Recommendation Summary

**Go with Option 3**: Two new models (ChatMessage + Notification)

**Rationale**:
1. Clean separation of concerns
2. No breaking changes
3. Simple to understand and query
4. Future-proof for dweller-to-dweller chat
5. Balanced complexity vs. functionality

**Next Steps**:
1. Get approval for Option 3
2. Create ChatMessage model
3. Run migrations
4. Update chat endpoint to persist messages
5. Integrate notifications with game events
6. Build frontend UI

**Estimated Time**: 10-12 hours total

---

## Questions to Answer

1. **Do we want chat history visible in the UI?**
   - Yes → Use ChatMessage
   - No → Maybe skip ChatMessage, use only Notification

2. **Do we want dweller-to-dweller conversations?**
   - Yes → Definitely need ChatMessage
   - No → Could simplify to just Notification

3. **Should notifications be dismissible?**
   - Already YES in current Notification model (is_dismissed field)

4. **How long should we keep chat history?**
   - Forever?
   - Auto-delete after 30 days?
   - Let user clear?

5. **Should we implement SSE fallback or WebSocket only?**
   - WebSocket only (simpler, modern browsers)
   - Add SSE later if needed

---

## Decision Needed

Please decide:
- [ ] **Option 1**: Chat + ChatMessage + Notification (3 models)
- [ ] **Option 2**: Extend LLMInteraction + Notification (reuse existing)
- [x] **Option 3**: ChatMessage + Notification (2 models) ⭐ **RECOMMENDED**

Once decided, we can proceed with implementation!
