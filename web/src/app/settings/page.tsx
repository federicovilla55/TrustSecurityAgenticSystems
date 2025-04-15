'use client';

import { signOut, useSession } from 'next-auth/react';
import { useRouter } from 'next/navigation';
import React, { useState } from 'react';

export default function SettingsPage() {
  const { data: session, status } = useSession();
  const router = useRouter();
  const [message, setMessage] = useState('');

  const backendUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  const token = session?.user?.accessToken;
  const username = session?.user?.name || '';
  const userInitial = username[0]?.toUpperCase() || '?';

  if (status === 'loading') {
    return <p>Loading...</p>;
  }

  if (!token) {
    router.push('/login');
    return null;
  }

  async function handleAgentAction(action: 'pause' | 'resume' | 'delete') {
    setMessage('');
    try {
      const res = await fetch(`${backendUrl}/api/${action}`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      const data = await res.json();
      if (!res.ok) {
        setMessage(data.detail || `${action} failed`);
      } else {
        setMessage(`${action} requested successfully`);
      }
    } catch (error) {
      setMessage(`${action} request failed.`);
      console.error(error);
    }
  }

  function goDashboard() {
    router.push('/dashboard');
  }

  async function logout() {
    await signOut({ callbackUrl: '/auth' });
  }

  return (
    <div className="min-h-screen bg-gray-100">
      <nav className="bg-white p-4 shadow flex justify-between items-center">
        <h1 className="text-xl font-bold">Settings</h1>
        <div className="flex items-center space-x-4">
          <div
            className="w-10 h-10 rounded-full bg-indigo-600 text-white flex items-center justify-center cursor-pointer"
            onClick={goDashboard}
            title="Go to Dashboard"
          >
            {userInitial}
          </div>
          <button
            className="text-sm text-red-600 hover:underline"
            onClick={logout}
          >
            Logout
          </button>
        </div>
      </nav>

      <main className="max-w-xl mx-auto p-4">
        {message && (
          <div className="my-2 p-2 bg-yellow-100 text-yellow-800 border border-yellow-300 rounded">
            {message}
          </div>
        )}
        <h2 className="text-2xl font-bold mb-4">Agent Controls</h2>
        <div className="space-y-2">
          <button
            className="bg-gray-600 text-white px-4 py-2 rounded"
            onClick={() => handleAgentAction('pause')}
          >
            Pause Agent
          </button>
          <button
            className="bg-green-600 text-white px-4 py-2 rounded"
            onClick={() => handleAgentAction('resume')}
          >
            Resume Agent
          </button>
          <button
            className="bg-red-600 text-white px-4 py-2 rounded"
            onClick={() => handleAgentAction('delete')}
          >
            Delete Agent
          </button>
        </div>
      </main>
    </div>
  );
}
