<script setup lang="ts">
import { ref } from 'vue';
import axios from '@/core/plugins/axios';

const email = ref('');
const error = ref('');
const success = ref(false);
const loading = ref(false);

const handleSubmit = async () => {
  error.value = '';

  if (!email.value) {
    error.value = 'Email is required';
    return;
  }

  loading.value = true;

  try {
    await axios.post('/api/v1/auth/forgot-password', {
      email: email.value
    });

    success.value = true;
  } catch (err: any) {
    error.value = err.response?.data?.detail || 'Failed to send reset email';
  } finally {
    loading.value = false;
  }
};
</script>

<template>
  <div class="login-container">
    <!-- Scanlines overlay -->
    <div class="scanlines"></div>

    <!-- CRT effect container -->
    <div class="crt-container flicker">
      <div class="login-box">
        <!-- Vault-Tec Header -->
        <div class="vault-header">
          <h1 class="terminal-title">VAULT-TEC INDUSTRIES</h1>
          <p class="terminal-subtitle">Password Recovery Terminal</p>
          <div class="terminal-line"></div>
        </div>

        <!-- Success Message -->
        <div v-if="success" class="success-message">
          <p>> RECOVERY EMAIL SENT</p>
          <p>> CHECK YOUR INBOX FOR RESET INSTRUCTIONS</p>
          <p>> IF EMAIL EXISTS IN SYSTEM, RESET LINK HAS BEEN DISPATCHED</p>
        </div>

        <!-- Recovery Form -->
        <form v-else @submit.prevent="handleSubmit" class="login-form">
          <div class="system-messages">
            <p class="system-msg">> PASSWORD RECOVERY PROTOCOL INITIATED</p>
            <p class="system-msg">> ENTER REGISTERED EMAIL ADDRESS...</p>
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
              :disabled="loading"
            />
          </div>

          <button type="submit" class="terminal-button" :disabled="loading">
            <span class="button-icon">►</span>
            {{ loading ? 'PROCESSING...' : 'SEND RESET LINK' }}
            <span class="button-icon">◄</span>
          </button>
        </form>

        <!-- Error Message -->
        <div v-if="error" class="error-message">
          <p>> ERROR: {{ error.toUpperCase() }}</p>
        </div>

        <!-- Back to Login -->
        <div class="register-link">
          <p class="terminal-text">
            > RETURN TO LOGIN:
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
/* Use same styling as LoginFormTerminal */
.login-container {
  min-height: 100vh;
  background: #000;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: 'Courier New', monospace;
  position: relative;
  overflow: hidden;
}

.scanlines {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: linear-gradient(
    transparent 50%,
    rgba(0, 255, 0, 0.03) 50%
  );
  background-size: 100% 4px;
  pointer-events: none;
  z-index: 1;
}

.crt-container {
  position: relative;
  z-index: 2;
  max-width: 600px;
  width: 90%;
}

.flicker {
  animation: flicker 0.15s ease-in-out infinite;
}

@keyframes flicker {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.95; }
}

.login-box {
  background: rgba(0, 0, 0, 0.9);
  border: 3px solid var(--color-theme-primary, #00ff00);
  padding: 2rem;
  box-shadow:
    0 0 20px var(--color-theme-glow, rgba(0, 255, 0, 0.3)),
    inset 0 0 20px rgba(0, 255, 0, 0.1);
}

.vault-header {
  text-align: center;
  margin-bottom: 2rem;
}

.terminal-title {
  color: var(--color-theme-primary, #00ff00);
  font-size: 2rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-shadow: 0 0 10px var(--color-theme-glow, rgba(0, 255, 0, 0.5));
  margin: 0;
}

.terminal-subtitle {
  color: var(--color-theme-primary, #00ff00);
  font-size: 0.9rem;
  margin-top: 0.5rem;
  opacity: 0.8;
}

.terminal-line {
  height: 2px;
  background: var(--color-theme-primary, #00ff00);
  margin-top: 1rem;
  box-shadow: 0 0 5px var(--color-theme-glow, rgba(0, 255, 0, 0.5));
}

.system-messages {
  margin-bottom: 1.5rem;
}

.system-msg {
  color: var(--color-theme-primary, #00ff00);
  font-size: 0.85rem;
  margin: 0.3rem 0;
  opacity: 0.7;
}

.login-form {
  margin-bottom: 1.5rem;
}

.form-group {
  margin-bottom: 1.5rem;
}

.terminal-label {
  display: block;
  color: var(--color-theme-primary, #00ff00);
  font-size: 0.9rem;
  margin-bottom: 0.5rem;
  text-transform: uppercase;
}

.terminal-input {
  width: 100%;
  padding: 0.75rem;
  background: rgba(0, 0, 0, 0.7);
  border: 2px solid var(--color-theme-primary, #00ff00);
  color: var(--color-theme-primary, #00ff00);
  font-family: 'Courier New', monospace;
  font-size: 1rem;
  outline: none;
  transition: all 0.3s ease;
}

.terminal-input:focus {
  box-shadow: 0 0 10px var(--color-theme-glow, rgba(0, 255, 0, 0.5));
  border-color: var(--color-theme-primary, #00ff00);
}

.terminal-input:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.terminal-input::placeholder {
  color: rgba(0, 255, 0, 0.4);
}

.terminal-button {
  width: 100%;
  padding: 1rem;
  background: rgba(0, 255, 0, 0.1);
  border: 2px solid var(--color-theme-primary, #00ff00);
  color: var(--color-theme-primary, #00ff00);
  font-family: 'Courier New', monospace;
  font-size: 1rem;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.3s ease;
  text-transform: uppercase;
  letter-spacing: 0.1em;
}

.terminal-button:hover:not(:disabled) {
  background: rgba(0, 255, 0, 0.2);
  box-shadow: 0 0 15px var(--color-theme-glow, rgba(0, 255, 0, 0.5));
}

.terminal-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.button-icon {
  margin: 0 0.5rem;
}

.error-message {
  background: rgba(255, 0, 0, 0.1);
  border: 2px solid #ff0000;
  padding: 1rem;
  margin-bottom: 1rem;
}

.error-message p {
  color: #ff0000;
  margin: 0.3rem 0;
  font-size: 0.85rem;
}

.success-message {
  background: rgba(0, 255, 0, 0.1);
  border: 2px solid var(--color-theme-primary, #00ff00);
  padding: 1.5rem;
  margin-bottom: 1rem;
}

.success-message p {
  color: var(--color-theme-primary, #00ff00);
  margin: 0.5rem 0;
  font-size: 0.85rem;
  text-align: center;
}

.register-link {
  text-align: center;
  margin-bottom: 1rem;
}

.terminal-text {
  color: var(--color-theme-primary, #00ff00);
  font-size: 0.85rem;
  margin: 0.5rem 0;
}

.link-text {
  color: var(--color-theme-primary, #00ff00);
  text-decoration: underline;
  cursor: pointer;
  transition: all 0.3s ease;
}

.link-text:hover {
  text-shadow: 0 0 5px var(--color-theme-glow, rgba(0, 255, 0, 0.7));
}

.terminal-footer {
  text-align: center;
  padding-top: 1rem;
  border-top: 1px solid rgba(0, 255, 0, 0.3);
}

.footer-text {
  color: var(--color-theme-primary, #00ff00);
  font-size: 0.7rem;
  margin: 0;
  opacity: 0.5;
}
</style>
