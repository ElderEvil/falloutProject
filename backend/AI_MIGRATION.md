# AI Service Migration to PydanticAI

This document describes the migration from direct OpenAI API calls to PydanticAI agents for dweller content generation.

## Overview

The `DwellerAIService` has been refactored to use PydanticAI agents, providing:
- **Multi-provider support**: Switch between OpenAI, Anthropic (Claude), and Ollama
- **Type-safe outputs**: Structured Pydantic models with automatic validation
- **Better error handling**: Automatic retries and validation
- **Cleaner code**: Separation of concerns between agents and service logic

## Architecture Changes

### New Files

```
backend/app/
├── agents/
│   ├── __init__.py
│   ├── deps.py                    # Dependency types for agent context
│   └── dweller_agents.py          # PydanticAI agent definitions
├── schemas/
│   └── dweller_ai.py              # Pydantic models for agent outputs
└── services/
    ├── dweller_ai.py              # Refactored service (uses agents)
    └── open_ai.py                 # Multi-provider model factory
```

### Configuration

**Environment Variables** (`.env`):
```bash
AI_PROVIDER=ollama              # Options: openai, anthropic, ollama
AI_MODEL=llama3.2               # Model name for the provider
OPENAI_API_KEY=                 # Optional: for OpenAI provider
ANTHROPIC_API_KEY=              # Optional: for Anthropic provider
OLLAMA_BASE_URL=http://localhost:11434/v1  # For Ollama provider
```

**Settings** (`app/core/config.py`):
```python
AI_PROVIDER: Literal["openai", "anthropic", "ollama"] = "ollama"
AI_MODEL: str = "llama3.2"
OPENAI_API_KEY: str | None = None
ANTHROPIC_API_KEY: str | None = None
OLLAMA_BASE_URL: str = "http://localhost:11434/v1"
```

## Agents

### 1. Backstory Agent
**Purpose**: Generates Fallout-style character biographies

**Input**: `BackstoryDeps`
- `first_name`: Dweller's first name
- `gender`: Gender for pronoun selection
- `special_stats`: Formatted SPECIAL stats string
- `location`: Origin location (Wasteland, Vault, etc.)

**Output**: `DwellerBackstory`
- `bio`: Biography string (600-900 characters recommended)

**Features**:
- Dynamic system prompt based on dweller context
- SPECIAL stats inform personality and skills
- Lore-accurate Fallout universe content
- Automatic length validation (with truncation fallback)

### 2. Bio Extension Agent
**Purpose**: Extends existing dweller biographies

**Input**: `ExtendBioDeps`
- `current_bio`: Existing biography to extend

**Output**: `ExtendedBio`
- `extended_bio`: Additional biographical content

**Features**:
- Maintains consistency with original bio
- Adds meaningful character development
- Preserves writing style and tone

### 3. Visual Attributes Agent
**Purpose**: Generates structured visual descriptions

**Input**: `VisualAttributesDeps`
- `first_name`: Dweller's first name
- `last_name`: Dweller's last name
- `gender`: Gender for attribute selection
- `bio`: Biography for context (optional)

**Output**: `DwellerVisualAttributes`
- `age`: Age category
- `height`, `eye_color`, `skin_tone`, `build`
- `hair_style`, `hair_color`
- `distinguishing_features`: List of unique traits
- `clothing_style`
- `facial_hair` (male only)
- `makeup` (female only)

**Features**:
- Type-safe structured output (no manual JSON parsing)
- Automatic validation of visual attributes
- Context-aware generation based on biography

## Service Methods

### Modified Methods

#### `generate_backstory()`
- **Before**: Manual prompt construction, message arrays, `textwrap.shorten()`
- **After**: PydanticAI agent with structured output, automatic validation
- **Benefits**: Type safety, better prompts, automatic retries

#### `extend_bio()`
- **Before**: Generic completion with manual message building
- **After**: Specialized bio extension agent with context injection
- **Benefits**: More focused prompts, consistent extensions

#### `generate_visual_attributes()`
- **Before**: Manual JSON generation/parsing with `json.loads()`
- **After**: Structured Pydantic output with automatic validation
- **Benefits**: No JSON parsing errors, type-safe attributes

### Unchanged Methods
- `generate_photo()` - Still uses OpenAI DALL-E directly
- `generate_audio()` - Still uses OpenAI TTS directly
- `generate_dweller_avatar()` - Orchestration only
- `dweller_generate_pipeline()` - Orchestration only

## Usage Examples

### Switching Providers

**Use OpenAI (GPT-4)**:
```bash
AI_PROVIDER=openai
AI_MODEL=gpt-4o
OPENAI_API_KEY=sk-...
```

**Use Anthropic (Claude)**:
```bash
AI_PROVIDER=anthropic
AI_MODEL=claude-3-5-sonnet-20241022
ANTHROPIC_API_KEY=sk-ant-...
```

**Use Ollama (Local)**:
```bash
AI_PROVIDER=ollama
AI_MODEL=llama3.2
OLLAMA_BASE_URL=http://localhost:11434/v1
```

### Agent Execution Flow

```python
# 1. Create dependencies
deps = BackstoryDeps(
    first_name="Marcus",
    gender=GenderEnum.MALE,
    special_stats="S:7, P:5, E:6, C:4, I:3, A:5, L:6",
    location="Wasteland"
)

# 2. Run agent
result = await backstory_agent.run(
    "Tell me about yourself, Marcus.",
    deps=deps
)

# 3. Access structured output
backstory = result.data.bio  # Type-safe access
```

## Benefits

### Type Safety
- No more `json.loads()` exceptions
- Automatic Pydantic validation
- IDE autocomplete for output fields

### Error Handling
- Automatic retries on validation failure
- Clear error messages
- Structured exception handling

### Testing
- Agents can be tested independently
- Mock dependencies easily
- Consistent output format

### Maintainability
- Clear separation of concerns
- Reusable agent definitions
- Easy to add new agents

## Migration Notes

### Backward Compatibility
✅ Same public API in `DwellerAIService`
✅ No changes to REST endpoints
✅ Database operations unchanged
✅ Existing tests should pass

### Breaking Changes
None - internal refactoring only

### Performance
- Similar latency to direct API calls
- Automatic retries may increase time on failures
- Structured output may require more tokens

## Troubleshooting

### Issue: "Exceeded maximum retries for output validation"
**Cause**: LLM output doesn't match Pydantic schema
**Solution**:
- Check agent prompts are clear about output format
- Adjust field constraints (e.g., remove strict `max_length`)
- Review LLM response in logs

### Issue: Biography too long
**Cause**: LLM ignores length constraints
**Solution**:
- Prompt emphasizes "600-900 characters"
- Safety truncation in service layer
- Consider using structured length guidance

### Issue: Model not found
**Cause**: Incorrect provider/model configuration
**Solution**:
- Verify `AI_PROVIDER` matches available providers
- Check `AI_MODEL` is valid for the provider
- Ensure API keys are set correctly

## Future Enhancements

- [ ] Add chat conversation agent for dweller interactions
- [ ] Create objective generation agent
- [ ] Implement quest narrative agent
- [ ] Add streaming support for long-form content
- [ ] Cost tracking and analytics per agent
- [ ] A/B testing different prompts
- [ ] Fine-tuning for Fallout lore
