# Fallout Shelter Game - Roadmap

## 🎯 **Core Vision: AI-Powered Dweller Interactions**

This is an **AI-first game** built on **PydanticAI**. The ultimate goal is rich, dynamic dweller interactions using AI agents with tool-calling capabilities.

---

## 🚀 **Phase 1: AI & Core Gameplay Loop** (HIGHEST PRIORITY)

### **1. Enhanced AI Dweller Chat with Tools** 🤖
**Status:** Partially Complete (Basic chat exists)
**Priority:** 🔥🔥🔥 CRITICAL

**What's Missing:**
- [ ] PydanticAI tool integration for dwellers
- [ ] Dwellers can request actions via chat (equip weapon, go explore, train stats)
- [ ] AI-driven personality responses based on SPECIAL stats
- [ ] Context-aware conversations (dweller remembers vault state, recent events)
- [ ] Multi-turn conversation memory
- [ ] Emotional state system influencing responses

**Backend Tasks:**
- Implement PydanticAI tools for dweller actions
- Create tool schemas for: equip_item, start_exploration, train_stat, change_room
- Add conversation context management
- Personality engine based on SPECIAL scores

**Frontend Tasks:**
- Enhanced chat UI with tool action previews
- Show when dweller is "thinking" or executing actions
- Visual feedback for tool calls (animations, confirmations)
- Chat history persistence

---

### **2. Weapons & Outfits System** ⚔️
**Status:** Backend exists, Frontend minimal
**Priority:** 🔥🔥🔥 CRITICAL

**Quick Integration:**
- [ ] Weapon/Outfit inventory UI
- [ ] Equip items to dwellers (drag-drop or click)
- [ ] Show equipped items on dweller cards
- [ ] Visual stat bonuses from equipment
- [ ] Loot system integration with wasteland

**Backend:** Already has weapon/outfit endpoints ✅
**Frontend:** Need equipment UI in dweller detail page

---

### **3. Combat System** ⚔️
**Status:** Not implemented
**Priority:** 🔥🔥🔥 CRITICAL

**What to Build:**
- [ ] Wasteland combat encounters
- [ ] Enemy types and difficulty
- [ ] Combat calculations (SPECIAL + weapon stats)
- [ ] Combat animations/feedback
- [ ] Loot drops from combat
- [ ] Dweller damage and health system
- [ ] Combat logs and history

**Integration Points:**
- Exploration system triggers combat
- Weapons/outfits affect combat outcomes
- AI chat can discuss combat strategies

---

### **4. Enhanced Wasteland Exploration** 🗺️
**Status:** Basic system exists
**Priority:** 🔥🔥 HIGH

**What's Missing:**
- [ ] Richer event system (encounters, discoveries, choices)
- [ ] Multi-stage explorations (journey with checkpoints)
- [ ] Resource discoveries (weapons, outfits, caps, junk)
- [ ] Danger/risk system based on dweller stats
- [ ] Visual exploration map/progress
- [ ] AI-generated exploration narratives

**Integration:**
- Combat encounters during exploration
- AI dwellers can tell stories about exploration
- Equipment affects exploration success

---

## 📦 **Phase 2: Polish & UX Quick Wins** (IMMEDIATE)

### **UI/UX Improvements**
- [ ] Loading skeletons (replace "Loading..." text)
- [ ] Empty states with friendly messages + CTAs
- [ ] Toast notifications for user actions
- [ ] Confirmation dialogs for destructive actions
- [ ] Better error messages with recovery suggestions
- [ ] Micro-animations (button clicks, state changes)
- [ ] Progress indicators for long operations
- [ ] Visual feedback for resource changes

### **Onboarding Experience**
- [ ] Welcome screen for new users
- [ ] First vault creation guide
- [ ] Interactive tutorial tooltips
- [ ] Quick tips for new overseers
- [ ] "Getting Started" checklist

### **Reward & Feedback System**
- [ ] Celebration animations for achievements
- [ ] Visual loot reveal system
- [ ] Level-up celebrations
- [ ] Milestone notifications
- [ ] Daily login rewards (optional)

---

## ✅ **Recently Completed Features**

### **Dweller Grid/List View** ✅
- ✅ Toggle between grid and list layouts
- ✅ View preference persistence in localStorage
- ✅ Responsive grid layout
- ✅ Integrated into filter panel

### **Dweller Detail Page** ✅
- ✅ Dedicated detail page with routing
- ✅ Three-tab layout (Profile, Stats, Equipment)
- ✅ Equipment tab placeholder
- ✅ AI portrait generation integration

### **Dweller Status System** ✅
- ✅ Backend: DwellerStatusEnum (IDLE, WORKING, EXPLORING, TRAINING, RESTING, DEAD)
- ✅ Auto-status updates on room assignment
- ✅ Filtering/sorting/search endpoints
- ✅ Frontend: Status badges, filter panel

### **User Authentication & Authorization** ✅
- ✅ Token refresh mechanism with Redis
- ✅ Email verification system
- ✅ Password reset flow

### **Email System** ✅
- ✅ Email verification, password reset, notifications
- ✅ MailHog for development
- ✅ Template-based HTML emails

### **Basic Wasteland Exploration** ✅
- ✅ Start, complete, recall mechanics
- ✅ Status integration
- ✅ Basic event system

---

## 🎯 **Phase 3: Advanced Features** (Future)

### **Inventory Management**
- Categorized inventory (weapons, outfits, junk, consumables)
- Item details and actions (equip, use, sell)
- Vault storage system
- Item crafting

### **User Profile Enhancement**
- Profile picture upload (MinIO integration)
- Statistics dashboard with charts
- Achievement/milestone display
- Customizable preferences
- Overseer rank/title system

### **Advanced AI Features**
- Dweller-to-dweller conversations
- AI-driven quests and storylines
- Dynamic event generation
- Personality evolution over time

### **Combat Expansion**
- Vault defense against raiders
- Boss encounters in wasteland
- Team-based combat
- Strategic combat choices

### **Game Features**
- Dweller breeding and children
- Radio room and recruitment
- Quest system expansion
- Trading system
- Achievements and badges
- PvP/Vault raids (optional)

---

## 🤖 **Automation & DevOps**

### **Current Infrastructure** ✅
- ✅ CI/CD pipelines (backend CI, build, deploy, rollback)
- ✅ Docker containerization
- ✅ Python 3.13 via uv package manager
- ✅ Pre-commit hooks (ruff, uv-lock)
- ✅ Dependabot (weekly updates)
- ✅ Semantic Release (automated versioning)

### **Planned**
- Security scanning workflow
- Performance regression testing
- Code quality metrics

---

## 📝 **Development Workflow**

### **Commit Message Format** (Conventional Commits)
```
feat: new feature           → Minor version bump (0.1.0 → 0.2.0)
fix: bug fix                → Patch version bump (0.1.0 → 0.1.1)
perf: performance           → Patch version bump
refactor: code refactor     → Patch version bump
docs: documentation         → No release
test: tests                 → No release
chore: maintenance          → No release
feat!: breaking change      → Major version bump (0.1.0 → 1.0.0)
```

---

## 🎯 **Next Sprint Focus**

### **Immediate (This Week):**
1. ✅ Grid/List view toggle (DONE)
2. Quick UX wins (loading states, toasts, empty states)
3. Equipment system UI (weapons/outfits display and equipping)
4. Enhanced dweller chat with tool integration

### **This Month:**
1. Combat system implementation
2. Enhanced wasteland exploration with combat
3. Loot and reward system
4. AI personality improvements

### **This Quarter:**
1. Full AI agent ecosystem for dwellers
2. Dynamic quest generation
3. Advanced combat mechanics
4. Mobile-responsive optimizations

---

## 📈 **Success Metrics**

- ✅ Zero manual version bumps
- ✅ Auto-generated documentation (CHANGELOG)
- ✅ Weekly dependency updates (Dependabot)
- Test coverage > 80%
- Performance budgets met (P95 < 1s)
- Zero critical security vulnerabilities
- **User engagement: Average session time > 15 minutes**
- **AI interactions: > 10 chat messages per session**

---

**Last Updated:** 2025-12-31
**Current Version:** See [CHANGELOG.md](../CHANGELOG.md) for latest version
