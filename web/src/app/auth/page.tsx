'use client';

import React, { useState, FormEvent } from 'react';
import { signIn } from 'next-auth/react';
import { useRouter } from 'next/navigation';

export default function AuthPage() {
  const router = useRouter();
  const [mode, setMode] = useState<'auth' | 'register'>('auth');

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');

  const [message, setMessage] = useState('');

  function toggleMode() {
    setMode(prev => (prev === 'auth' ? 'register' : 'auth'));
    setMessage('');
  }

  function isValidUsername(name: string): boolean {
    const validPattern = /^[a-zA-Z0-9_-]+$/;
    return validPattern.test(name);
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setMessage('');

    if (mode === 'register') {
      // Registration case, first check if the username is valid, then send the request to the backend.
      if (!isValidUsername(username)) {
        // Username must not contain characters that may interference with AutoGen framework.
        setMessage(
          `Invalid name: ${username}. Only letters, numbers, '_' and '-' are allowed.`
        );
        return;
      }

      try {
        const res = await fetch('http://localhost:8000/api/register', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ username, password }),
        });
        const data = await res.json();

        if (!res.ok) {
          setMessage(data.detail || 'Registration failed.');
        } else {
          setMessage(data.status || 'Registration successful!');

          // Data for indirect sign in using credentials for registration.
          const formData = new URLSearchParams();
          formData.append('username', username);
          formData.append('password', password);

          const result = await signIn('credentials', {
            redirect: false,
            username,
            password,
          });

          if (result?.error) {
            // Show errors.
            setMessage(result.error);
          } else {
            // If there are no errors, redirect to the dashboard as the user completed the login/registration.
            router.push('/dashboard');
          }
        }
      } catch (error) {
        console.error('Error during registration:', error);
        setMessage('Registration request failed.');
      }
    } else {
      // Sign In case
      try {
        const formData = new URLSearchParams();
        formData.append('username', username);
        formData.append('password', password);

        // Sign In using user provided (via form) parameters.
        const result = await signIn('credentials', {
          redirect: false,
          username,
          password,
        });

        if (result?.error) {
          setMessage(result.error);
        } else {
          // If no errors found, redirect to the dashboard.
          router.push('/dashboard');
        }

      } catch (error) {
        console.error('Error during auth:', error);
        setMessage('Login request failed.');
      }
    }
  }

  // Show HTML code for the overall page.
  return (
    <div className="min-h-screen flex items-center justify-center text-black p-4">
      <div className="max-w-md w-full bg-white p-6 rounded shadow">
        <h1 className="text-2xl font-bold mb-4 text-center">
          {mode === 'auth' ? 'Login' : 'Register'}
        </h1>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium">Username</label>
            <input
              type="text"
              className="border w-full p-2 rounded"
              value={username}
              onChange={e => setUsername(e.target.value)}
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium">Password</label>
            <input
              type="password"
              className="border w-full p-2 rounded"
              value={password}
              onChange={e => setPassword(e.target.value)}
              required
            />
          </div>

          <button
            type="submit"
            className="bg-indigo-600 text-white w-full py-2 rounded hover:bg-indigo-700 transition"
          >
            {mode === 'auth' ? 'Login' : 'Register'}
          </button>
        </form>

        <p className="mt-4 text-center">
          {mode === 'auth'
            ? "Don't have an account?"
            : 'Already have an account?'}{' '}
          <button onClick={toggleMode} className="text-indigo-600 underline">
            {mode === 'auth' ? 'Register' : 'Login'}
          </button>
        </p>

        {message && (
          <p className="mt-4 p-2 bg-yellow-100 text-yellow-800 border border-yellow-300 rounded">
            {message}
          </p>
        )}
      </div>
    </div>
  );
}
