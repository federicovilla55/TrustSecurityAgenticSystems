'use client';

import React, { useState, FormEvent } from 'react';
import { useRouter } from 'next/navigation';

export default function AuthPage() {
  const router = useRouter();
  // Toggle between login or register mode
  const [mode, setMode] = useState<'login' | 'register'>('login');

  // Form fields
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');

  // For user feedback (success/error messages)
  const [message, setMessage] = useState('');

  // Toggle the mode between "login" and "register"
  function toggleMode() {
    setMode(prev => (prev === 'login' ? 'register' : 'login'));
    setMessage('');
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setMessage('');

    if (mode === 'register') {
      // 1) Call FastAPI /api/register with JSON body
      try {
        const res = await fetch('http://localhost:8000/api/register', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ username, password }),
        });
        const data = await res.json();

        if (!res.ok) {
          // If 400 or some error, show message
          setMessage(data.detail || 'Registration failed.');
        } else {
          // 200 => success
          setMessage(data.status || 'Registration successful!');
        }
      } catch (error) {
        console.error('Error during registration:', error);
        setMessage('Registration request failed.');
      }
    } else {
      // mode === 'login'
      // 2) Call FastAPI /api/token with form data
      try {
        const formData = new URLSearchParams();
        formData.append('username', username);
        formData.append('password', password);

        const res = await fetch('http://localhost:8000/api/token', {
          method: 'POST',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
          body: formData.toString(),
        });
        const data = await res.json();

        if (!res.ok) {
          // If 401 or some error, show message
          setMessage(data.detail || 'Login failed.');
        } else {
          // Successful => store token, redirect to /dashboard
          localStorage.setItem('access_token', data.access_token);
          router.push('/dashboard');
        }
      } catch (error) {
        console.error('Error during login:', error);
        setMessage('Login request failed.');
      }
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-200 p-4">
      <div className="max-w-md w-full bg-white p-6 rounded shadow">
        <h1 className="text-2xl font-bold mb-4 text-center">
          {mode === 'login' ? 'Login' : 'Register'}
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
            {mode === 'login' ? 'Login' : 'Register'}
          </button>
        </form>

        <p className="mt-4 text-center">
          {mode === 'login'
            ? "Don't have an account?"
            : 'Already have an account?'}{' '}
          <button onClick={toggleMode} className="text-indigo-600 underline">
            {mode === 'login' ? 'Register' : 'Login'}
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
