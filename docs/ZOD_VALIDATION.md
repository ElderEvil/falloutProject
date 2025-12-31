Below are **clean, copy‑pasteable Zod examples** tailored exactly to what you
listed, using patterns that work well with **Vue (Composition API)** and a
FastAPI backend.

I’ll keep them **practical**, not abstract.

---

# 1) Profile – user input validation

Typical fields:

- display name
- bio
- avatar URL
- preferences

```ts
import { z } from "zod";

export const ProfileSchema = z.object({
  displayName: z
    .string()
    .min(3, "Display name too short")
    .max(32, "Display name too long")
    .regex(/^[a-zA-Z0-9_ ]+$/, "Invalid characters"),

  bio: z
    .string()
    .max(160, "Bio too long")
    .optional(),

  avatarUrl: z
    .string()
    .url("Invalid avatar URL")
    .optional(),

  isPublic: z.boolean(),
});

export type ProfileInput = z.infer<typeof ProfileSchema>;
```

### Vue usage (form submit)

```ts
function submitProfile(form: unknown) {
  const parsed = ProfileSchema.safeParse(form);

  if (!parsed.success) {
    errors.value = parsed.error.flatten().fieldErrors;
    return;
  }

  api.updateProfile(parsed.data);
}
```

Why this is good:

- frontend-only UX validation
- instant feedback
- backend remains authoritative

---

# 2) User message validation (chat / inbox)

For a game, you usually want:

- length limits
- profanity prevention (placeholder)
- anti-spam shaping

```ts
export const UserMessageSchema = z.object({
  message: z
    .string()
    .trim()
    .min(1, "Message cannot be empty")
    .max(500, "Message too long"),

  channel: z.enum(["global", "guild", "private"]),

  recipientId: z.string().uuid().optional(),
}).refine(
  (data) =>
    data.channel !== "private" || Boolean(data.recipientId),
  {
    message: "Private messages require a recipient",
    path: ["recipientId"],
  }
);

export type UserMessageInput = z.infer<typeof UserMessageSchema>;
```

### Vue usage

```ts
function sendMessage(payload: unknown) {
  const parsed = UserMessageSchema.safeParse(payload);

  if (!parsed.success) {
    toast.error(parsed.error.errors[0].message);
    return;
  }

  api.sendMessage(parsed.data);
}
```

✅ This prevents:

- empty spam
- malformed private messages
- invalid channels

---

# 3) Login validation

Focus on:

- fast feedback
- minimal rules
- avoid leaking backend constraints

```ts
export const LoginSchema = z.object({
  email: z
    .string()
    .email("Invalid email"),

  password: z
    .string()
    .min(8, "Password too short")
    .max(128),
});

export type LoginInput = z.infer<typeof LoginSchema>;
```

### Vue usage

```ts
function login(form: unknown) {
  const parsed = LoginSchema.safeParse(form);

  if (!parsed.success) {
    errors.value = parsed.error.flatten().fieldErrors;
    return;
  }

  api.login(parsed.data);
}
```

---

# 4) Register validation (with password confirmation)

This is where Zod shines.

```ts
export const RegisterSchema = z.object({
  email: z
    .string()
    .email(),

  username: z
    .string()
    .min(3)
    .max(24)
    .regex(/^[a-zA-Z0-9_]+$/, "Invalid username"),

  password: z
    .string()
    .min(8)
    .max(128),

  confirmPassword: z.string(),
}).refine(
  (data) => data.password === data.confirmPassword,
  {
    message: "Passwords do not match",
    path: ["confirmPassword"],
  }
);

export type RegisterInput = z.infer<typeof RegisterSchema>;
```

### Vue usage

```ts
function register(form: unknown) {
  const parsed = RegisterSchema.safeParse(form);

  if (!parsed.success) {
    errors.value = parsed.error.flatten().fieldErrors;
    return;
  }

  api.register(parsed.data);
}
```

---

# 5) Optional: reuse rules cleanly

Avoid duplication:

```ts
const Password = z.string().min(8).max(128);

export const LoginSchema = z.object({
  email: z.string().email(),
  password: Password,
});

export const RegisterSchema = z.object({
  email: z.string().email(),
  username: z.string().min(3),
  password: Password,
  confirmPassword: z.string(),
}).refine((d) => d.password === d.confirmPassword, {
  path: ["confirmPassword"],
});
```

---

# 6) Common pitfalls (important)

❌ Don’t trust Zod for security
✅ Always validate again in FastAPI

❌ Don’t mirror Pydantic 1:1
✅ Use Zod for UX & client-side safety

❌ Don’t over-validate (e.g. password strength rules)
✅ Let backend decide hard rules

---

# Final recommendation for your game

Use Zod:

- on **form submit**
- before **sending messages**
- when **reading localStorage**
- when **accepting API responses into stores**

This gives you:

- excellent UX
- fewer backend errors
- safer refactors
