'use client';

import React, { useEffect, useState, FormEvent } from 'react';
import { useSession, signOut } from 'next-auth/react';
import { useRouter } from 'next/navigation';

interface AgentInformation {
  policies: Array<{ rule_ID: string; content: string }> | null;
  public_information: Array<{ info_ID: string; content: string }> | null;
  private_information: Array<{ [key: string]: any }> | null; // or refine as needed
  isSetup: boolean;
}

export default function DashboardPage() {
  const { data: session, status } = useSession();
  const router = useRouter();

  const [info, setInfo] = useState<AgentInformation | null>(null);
  const [editing, setEditing] = useState(false);

  // Editing states for the textareas
  const [editedPolicies, setEditedPolicies] = useState('');
  const [editedPublic, setEditedPublic] = useState('');
  const [editedPrivate, setEditedPrivate] = useState('');

  // Setup flow
  const [setupContent, setSetupContent] = useState('');

  // For user feedback
  const [message, setMessage] = useState('');

  // Adjust this to match your real backend
  const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

  useEffect(() => {
    if (status === 'loading') return; // still checking session
    if (status === 'unauthenticated') {
      router.push('/auth');
      return;
    }

    // Fetch data once authenticated
    fetchAgentInformation();
  }, [status]);

  // Fetch agent data from FastAPI
  async function fetchAgentInformation() {
    if (!session?.user?.accessToken) return;
    setMessage('');

    try {
      const res = await fetch(`${API_URL}/api/get_information`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${session.user.accessToken}`,
        },
        body: JSON.stringify({ type: 7 }), // or whichever request type you need
      });

      if (!res.ok) {
        if (res.status === 401) {
          await signOut();
        } else {
          const errData = await res.json().catch(() => ({}));
          setMessage(errData.detail || 'Error fetching info');
        }
        return;
      }

      const data: AgentInformation = await res.json();
      setInfo(data);
    } catch (error) {
      console.error(error);
      setMessage('Failed to fetch info');
    }
  }

  // Setup flow if agent is not set up
  async function handleSetup(e: FormEvent) {
    e.preventDefault();
    if (!session?.user?.accessToken) return;
    setMessage('');

    try {
      const res = await fetch(`${API_URL}/api/setup`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${session.user.accessToken}`,
        },
        body: JSON.stringify({
          user: session.user.id || session.user.name,
          content: setupContent,
        }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        setMessage(errData.detail || 'Error during setup');
        return;
      }

      setMessage('Setup successful!');
      setSetupContent('');
      // Refresh info
      fetchAgentInformation();
    } catch (error) {
      console.error(error);
      setMessage('Setup request failed.');
    }
  }

  // Editing logic
  function startEditing() {
    if (!info) return;
    setMessage('');

    // Convert each field to JSON text, defaulting to empty arrays if null
    setEditedPolicies(JSON.stringify(info.policies || [], null, 2));
    setEditedPublic(JSON.stringify(info.public_information || [], null, 2));
    setEditedPrivate(JSON.stringify(info.private_information || [], null, 2));

    setEditing(true);
  }

  function cancelEditing() {
    setEditing(false);
    setMessage('');
  }

  async function saveEdits() {
    if (!session?.user?.accessToken) return;

    let parsedPolicies, parsedPublic, parsedPrivate;
    try {
      parsedPolicies = JSON.parse(editedPolicies);
      parsedPublic = JSON.parse(editedPublic);
      parsedPrivate = JSON.parse(editedPrivate);
    } catch (err) {
      setMessage('Error parsing JSON. Please ensure valid JSON format.');
      return;
    }

    const requestBody = {
      user: session.user.id || session.user.name || 'unknown_user',
      policies: parsedPolicies,
      public_information: parsedPublic,
      private_information: parsedPrivate,
    };

    try {
      const res = await fetch(`${API_URL}/api/change_information`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${session.user.accessToken}`,
        },
        body: JSON.stringify(requestBody),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        setMessage(errData.detail || 'Error saving changes.');
        return;
      }

      setMessage('Changes saved successfully!');
      setEditing(false);
      // Refresh updated info
      await fetchAgentInformation();
    } catch (error) {
      console.error(error);
      setMessage('Request to change_information failed.');
    }
  }

  function handleSignOut() {
    signOut();
  }

  // If session is still loading or unauth, just show placeholders
  if (status === 'loading') {
    return <p>Loading session...</p>;
  }
  if (status === 'unauthenticated') {
    router.push('/auth');
    return null;
  }

  return (
    <div className="p-4 max-w-4xl mx-auto">
      {/* Top bar */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <button
          onClick={handleSignOut}
          className="bg-red-600 text-white px-4 py-2 rounded"
        >
          Sign Out
        </button>
      </div>

      {/* Display messages */}
      {message && (
        <p className="my-2 p-2 bg-yellow-100 border border-yellow-300 text-yellow-800 rounded">
          {message}
        </p>
      )}

      {/* If info not yet fetched, show a placeholder */}
      {!info && <p>Loading agent information...</p>}

      {info && (
        <>
          {!info.isSetup ? (
            // ---- NOT SETUP => SHOW SETUP FORM ----
            <div className="p-4 border rounded bg-gray-100">
              <h2 className="text-lg font-semibold">
                Your agent is not set up yet
              </h2>
              <p className="text-sm text-gray-600 mb-3">
                Provide some setup content:
              </p>
              <form onSubmit={handleSetup}>
                <textarea
                  className="w-full p-2 border rounded mb-2"
                  value={setupContent}
                  onChange={(e) => setSetupContent(e.target.value)}
                  placeholder="Enter your setup data..."
                />
                <button
                  type="submit"
                  className="bg-blue-600 text-white px-4 py-2 rounded"
                >
                  Complete Setup
                </button>
              </form>
            </div>
          ) : (
            // ---- isSetup === true ----
            <>
              {/* If all three are null => Setup in progress */}
              {info.policies === null &&
              info.public_information === null &&
              info.private_information === null ? (
                <p className="font-semibold text-orange-700">
                  Setup in progress...
                </p>
              ) : !editing ? (
                // ------ STATIC VIEW (SHOW ONLY "content") ------
                <div className="relative border p-4 rounded bg-gray-50">
                  {/* Pencil icon => start editing */}
                  <button
                    onClick={startEditing}
                    className="absolute top-2 right-2"
                    title="Edit"
                  >
                    ✏️
                  </button>

                  <h2 className="text-lg font-semibold mb-1">Policies</h2>
                  {info.policies && info.policies.length > 0 ? (
                    <ul className="list-disc list-inside pl-4 mb-4">
                      {info.policies.map((item, idx) => (
                        <li key={idx}>{item.content}</li>
                      ))}
                    </ul>
                  ) : (
                    <p className="italic mb-4">No policies</p>
                  )}

                  <h2 className="text-lg font-semibold mb-1">
                    Public Information
                  </h2>
                  {info.public_information &&
                  info.public_information.length > 0 ? (
                    <ul className="list-disc list-inside pl-4 mb-4">
                      {info.public_information.map((item, idx) => (
                        <li key={idx}>{item.content}</li>
                      ))}
                    </ul>
                  ) : (
                    <p className="italic mb-4">No public information</p>
                  )}

                  <h2 className="text-lg font-semibold mb-1">
                    Private Information
                  </h2>
                  {info.private_information &&
                  info.private_information.length > 0 ? (
                    <ul className="list-disc list-inside pl-4 mb-4">
                      {info.private_information.map((item, idx) => (
                        <li key={idx}>{item.content}</li>
                      ))}
                    </ul>
                  ) : (
                    <p className="italic">No private information</p>
                  )}
                </div>
              ) : (
                // ------ EDITING VIEW ------
                <div className="border p-4 rounded bg-white">
                  <h2 className="text-lg font-semibold mb-2">
                    Edit Policies (JSON)
                  </h2>
                  <textarea
                    className="w-full border p-2 rounded h-40 mb-4"
                    value={editedPolicies}
                    onChange={(e) => setEditedPolicies(e.target.value)}
                  />

                  <h2 className="text-lg font-semibold mb-2">
                    Edit Public Information (JSON)
                  </h2>
                  <textarea
                    className="w-full border p-2 rounded h-40 mb-4"
                    value={editedPublic}
                    onChange={(e) => setEditedPublic(e.target.value)}
                  />

                  <h2 className="text-lg font-semibold mb-2">
                    Edit Private Information (JSON)
                  </h2>
                  <textarea
                    className="w-full border p-2 rounded h-40 mb-4"
                    value={editedPrivate}
                    onChange={(e) => setEditedPrivate(e.target.value)}
                  />

                  <div className="flex gap-2 mt-4">
                    <button
                      onClick={saveEdits}
                      className="bg-green-600 text-white px-4 py-2 rounded"
                    >
                      Save
                    </button>
                    <button
                      onClick={cancelEditing}
                      className="bg-gray-300 px-4 py-2 rounded"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
}
