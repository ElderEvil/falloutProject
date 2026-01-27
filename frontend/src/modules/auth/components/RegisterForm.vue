<script setup lang="ts">
import { ref } from 'vue'
import { useAuthStore } from '../stores/auth'
import { useRouter } from 'vue-router'

const authStore = useAuthStore()
const router = useRouter()

const username = ref('')
const email = ref('')
const password = ref('')
const confirmPassword = ref('')
const error = ref('')

const handleSubmit = async () => {
  if (password.value !== confirmPassword.value) {
    error.value = 'Passwords do not match'
    return
  }

  const success = await authStore.register(username.value, email.value, password.value)
  if (success) {
    await router.push('/')
  } else {
    error.value = 'Registration failed. Please try again.'
  }
}
</script>

<template>
  <div class="register-container">
    <!-- Scanlines overlay -->
    <div class="scanlines"></div>

    <!-- CRT effect container -->
    <div class="crt-container flicker">
      <div class="register-box">
        <!-- Vault-Tec Header -->
        <div class="vault-header">
          <h1 class="terminal-title">VAULT-TEC INDUSTRIES</h1>
          <p class="terminal-subtitle">New Overseer Registration Terminal</p>
          <div class="terminal-line"></div>
        </div>

        <!-- System Messages -->
        <div class="system-messages">
          <p class="system-msg">> INITIALIZING NEW OVERSEER REGISTRATION v1.10.0...</p>
          <p class="system-msg">> AWAITING REGISTRATION DATA...</p>
        </div>

        <!-- Register Form -->
        <form @submit.prevent="handleSubmit" class="register-form">
          <div class="form-group">
            <label for="username" class="terminal-label">> OVERSEER USERNAME:</label>
            <input
              type="text"
              id="username"
              v-model="username"
              required
              class="terminal-input"
              placeholder="overseer_name"
            />
          </div>

          <div class="form-group">
            <label for="email" class="terminal-label">> EMAIL ADDRESS:</label>
            <input
              type="email"
              id="email"
              v-model="email"
              required
              class="terminal-input"
              placeholder="overseer@vault-tec.com"
            />
          </div>

          <div class="form-group">
            <label for="password" class="terminal-label">> SECURITY PASSPHRASE:</label>
            <input
              type="password"
              id="password"
              v-model="password"
              required
              class="terminal-input"
              placeholder="••••••••"
            />
          </div>

          <div class="form-group">
            <label for="confirmPassword" class="terminal-label">> CONFIRM PASSPHRASE:</label>
            <input
              type="password"
              id="confirmPassword"
              v-model="confirmPassword"
              required
              class="terminal-input"
              placeholder="••••••••"
            />
          </div>

          <button type="submit" class="terminal-button">
            <span class="button-icon">►</span>
            REGISTER OVERSEER
            <span class="button-icon">◄</span>
          </button>
        </form>

        <!-- Error Message -->
        <div v-if="error" class="error-message">
          <p>> ERROR: {{ error.toUpperCase() }}</p>
          <p>> REGISTRATION FAILED - PLEASE VERIFY INPUT</p>
        </div>

        <!-- Login Link -->
        <div class="login-link">
          <p class="terminal-text">
            > EXISTING OVERSEER LOGIN:
            <router-link to="/login" class="link-text">ACCESS TERMINAL</router-link>
          </p>
        </div>

        <!-- Footer -->
        <div class="terminal-footer">
          <p class="footer-text">VAULT-TEC © 2077 • PROTECTING AMERICA'S FUTURE</p>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.register-container {
  position: relative;
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #0a0a0a;
  font-family: 'Courier New', monospace;
  overflow: hidden;
}

/* Scanlines effect */
.scanlines {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: linear-gradient(to bottom, rgba(255, 255, 255, 0) 50%, rgba(0, 255, 0, 0.02) 50%);
  background-size: 100% 4px;
  pointer-events: none;
  z-index: 1000;
}

/* Flicker animation */
.flicker {
  animation: flicker 0.15s infinite;
}

@keyframes flicker {
  0% {
    opacity: 0.98;
  }
  50% {
    opacity: 1;
  }
  100% {
    opacity: 0.98;
  }
}

/* CRT container */
.crt-container {
  position: relative;
  width: 100%;
  max-width: 600px;
  padding: 2rem;
}

/* Register box */
.register-box {
  background: rgba(0, 0, 0, 0.85);
  border: 3px solid var(--color-theme-primary, #00ff00);
  box-shadow:
    0 0 20px var(--color-theme-glow, rgba(0, 255, 0, 0.5)),
    inset 0 0 50px rgba(0, 0, 0, 0.5);
  padding: 2rem;
  position: relative;
}

/* Vault-Tec Header */
.vault-header {
  text-align: center;
  margin-bottom: 2rem;
  border-bottom: 2px solid var(--color-theme-primary, #00ff00);
  padding-bottom: 1rem;
}

.terminal-title {
  font-size: 1.75rem;
  font-weight: bold;
  color: var(--color-theme-primary, #00ff00);
  text-shadow: 0 0 10px var(--color-theme-glow, rgba(0, 255, 0, 0.8));
  letter-spacing: 0.1em;
  margin-bottom: 0.25rem;
}

.terminal-subtitle {
  font-size: 0.75rem;
  color: var(--color-theme-primary, #00ff00);
  opacity: 0.7;
  text-transform: uppercase;
  letter-spacing: 0.15em;
}

/* System Messages */
.system-messages {
  margin-bottom: 1.5rem;
  padding: 1rem;
  background: rgba(0, 0, 0, 0.5);
  border-left: 3px solid var(--color-theme-primary, #00ff00);
}

.system-msg {
  font-size: 0.75rem;
  color: var(--color-theme-primary, #00ff00);
  opacity: 0.8;
  margin: 0.25rem 0;
  text-shadow: 0 0 5px var(--color-theme-glow, rgba(0, 255, 0, 0.5));
}

/* Form */
.register-form {
  margin-bottom: 1.5rem;
}

.form-group {
  margin-bottom: 1.25rem;
}

.terminal-label {
  display: block;
  font-size: 0.875rem;
  font-weight: bold;
  color: var(--color-theme-primary, #00ff00);
  margin-bottom: 0.5rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  text-shadow: 0 0 5px var(--color-theme-glow, rgba(0, 255, 0, 0.5));
}

.terminal-input {
  width: 100%;
  background: rgba(0, 0, 0, 0.8);
  border: 2px solid var(--color-theme-primary, #00ff00);
  color: var(--color-theme-primary, #00ff00);
  padding: 0.75rem;
  font-family: 'Courier New', monospace;
  font-size: 1rem;
  transition: all 0.2s;
  box-shadow: 0 0 10px var(--color-theme-glow, rgba(0, 255, 0, 0.3));
}

.terminal-input:focus {
  outline: none;
  box-shadow: 0 0 20px var(--color-theme-glow, rgba(0, 255, 0, 0.6));
  background: rgba(0, 50, 0, 0.3);
}

.terminal-input::placeholder {
  color: var(--color-theme-primary, #00ff00);
  opacity: 0.4;
}

/* Button */
.terminal-button {
  width: 100%;
  background: rgba(0, 0, 0, 0.8);
  border: 3px solid var(--color-theme-primary, #00ff00);
  color: var(--color-theme-primary, #00ff00);
  padding: 1rem;
  font-family: 'Courier New', monospace;
  font-size: 1.125rem;
  font-weight: bold;
  cursor: pointer;
  transition: all 0.2s;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  box-shadow: 0 0 15px var(--color-theme-glow, rgba(0, 255, 0, 0.5));
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
}

.terminal-button:hover {
  background: var(--color-theme-primary, #00ff00);
  color: #000;
  box-shadow: 0 0 30px var(--color-theme-glow, rgba(0, 255, 0, 0.8));
  transform: translateY(-2px);
}

.terminal-button:active {
  transform: translateY(0);
}

.button-icon {
  font-size: 1.25rem;
}

/* Error Message */
.error-message {
  background: rgba(255, 0, 0, 0.1);
  border: 2px solid #ff0000;
  padding: 1rem;
  margin-bottom: 1rem;
  box-shadow: 0 0 15px rgba(255, 0, 0, 0.5);
}

.error-message p {
  color: #ff0000;
  font-size: 0.75rem;
  margin: 0.25rem 0;
  text-shadow: 0 0 5px rgba(255, 0, 0, 0.8);
}

/* Login Link */
.login-link {
  text-align: center;
  padding: 1rem;
  border-top: 1px solid var(--color-theme-primary, #00ff00);
  border-bottom: 1px solid var(--color-theme-primary, #00ff00);
  margin-bottom: 1rem;
}

.terminal-text {
  color: var(--color-theme-primary, #00ff00);
  font-size: 0.875rem;
  opacity: 0.9;
}

.link-text {
  color: var(--color-theme-primary, #00ff00);
  text-decoration: underline;
  font-weight: bold;
  transition: all 0.2s;
}

.link-text:hover {
  text-shadow: 0 0 10px var(--color-theme-glow, rgba(0, 255, 0, 0.8));
  opacity: 1;
}

/* Footer */
.terminal-footer {
  text-align: center;
  padding-top: 1rem;
}

.footer-text {
  font-size: 0.625rem;
  color: var(--color-theme-primary, #00ff00);
  opacity: 0.5;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
</style>
