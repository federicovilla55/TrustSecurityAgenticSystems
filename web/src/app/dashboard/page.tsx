'use client';

import React, {useEffect, useState, FormEvent, useRef} from 'react';
import { useSession, signOut } from 'next-auth/react';
import { useRouter } from 'next/navigation';

interface AgentInformation {
  policies: string | null;
  public_information: string | null;
  private_information: string | null;
  isSetup: boolean;
}

interface SettingMenuProperties {
  onSignOut: () => void;
  username: string;
  info: AgentInformation | null;
}

interface MessageType {
  id: string;
  text: string;
  visible: boolean;
}

// Dropdown menu redirect to settings and logout buttons.
const ProfileDropdown = ({ onSignOut, username, info }: SettingMenuProperties) => {
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const userInitial = username?.charAt(0)?.toUpperCase() || 'U';
  const router = useRouter();

  // If escape key button is pressed or a mouse click event happens, then close the menu.
  useEffect(() => {
  const handleKeyDown = (event: KeyboardEvent) => {
    if (event.key === 'Escape') {
      setIsDropdownOpen(false);
    }
  };
  document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, []);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsDropdownOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => setIsDropdownOpen(!isDropdownOpen)}
        className="w-10 h-10 rounded-full bg-gray-300 flex items-center justify-center hover:bg-gray-400 transition-colors"
        aria-haspopup="true"
        aria-expanded={isDropdownOpen}
      >
        <span className="text-gray-700 font-medium">{userInitial}</span>
      </button>

      {isDropdownOpen && (
        <div
          className="absolute right-0 mt-2 w-48 bg-white rounded-md shadow-lg py-1 ring-1 ring-black ring-opacity-5"
          role="menu"
          style={{ zIndex: 1000 }}
        >
          <div className="px-4 py-2 text-sm text-gray-900 font-semibold border-b border-gray-200">
            {username}
          </div>

          {info && info.isSetup && (
            <button
              onClick={() => {
                router.push('/settings');
                setIsDropdownOpen(false);
              }}
              className="block px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 w-full text-left"
              role="menuitem"
            >
              Settings
            </button>
          )}
          <button
            onClick={() => {
              onSignOut();
              setIsDropdownOpen(false);
            }}
            className="block px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 w-full text-left"
            role="menuitem"
          >
            Sign Out
          </button>
        </div>
      )}
    </div>
  );
};

// Main dashboard page
export default function DashboardPage() {
  const { data: session, status } = useSession();
  const router = useRouter();

  const [info, setInfo] = useState<AgentInformation | null>(null);
  const [editing, setEditing] = useState(false);

  const [editedPolicies, setEditedPolicies] = useState('');
  const [editedPublic, setEditedPublic] = useState('');
  const [editedPrivate, setEditedPrivate] = useState('');

  const [resetConnections, setResetConnections] = useState(false);

  const [sentDecisions, setSentDecisions] = useState<Record<string, string>>({});

  const [isSubmitting, setIsSubmitting] = useState(false);

  const [setupContent, setSetupContent] = useState('');

  const [message, setMessage] = useState('');
  const [messages, setMessages] = useState<MessageType[]>([]);

  const timersRef = useRef<Record<string, NodeJS.Timeout>>({});

  const [suggestedAgents, setSuggestedAgents] = useState<Record<string, string>>({});
  const [processingAgent, setProcessingAgent] = useState<string | null>(null);

  const [strictnessValue, setStrictnessValue] = useState<number | null>(null);

  const [establishedRelations, setEstablishedRelations] = useState<Record<string, string>>({});

  const strictnessOptions = [
    {
      value: 0,
      description: "Connect with anyone sharing common interests (e.g., hobbies, projects)."
    },
    {
      value: 1,
      description: "Connect with users in the same industry (e.g., tech, healthcare)."
    },
    {
      value: 2,
      description: "Connect only with users from the same organization/company."
    },
    {
      value: 3,
      description: "Connect with users from the same organization AND similar job title/role (e.g., 'Senior Engineer at Microsoft')."
    }
  ];


  const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

  useEffect(() => {
    if (status === 'loading') return;
    if (status === 'unauthenticated') {
      router.push('/auth');
      return;
    }

    fetchAgentInformation();
  }, [status]);

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
        body: JSON.stringify({ type: 7 }),
      });

      if (!res.ok) {
        if (res.status === 401) {
          await signOut();
        } else {
          const errData = await res.json().catch(() => ({}));
          addMessage(errData.detail || 'Error fetching info');
        }
        return;
      }

      const data: AgentInformation = await res.json();
      setInfo(data);
    } catch (error) {
      console.error(error);
      addMessage('Failed to fetch info');
    }
  }

  const handleFeedback = async (receiver: string, feedback: number) => {
    setProcessingAgent(receiver);
    try {
      const response = await fetch(`${API_URL}/api/feedback`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${session?.user?.accessToken}`
        },
        body: JSON.stringify({
          receiver: receiver,
          feedback: feedback,
        }),
      });

      if (!response.ok) throw new Error('Feedback failed');

      setSuggestedAgents(prev => {
        const updated = { ...prev };
        delete updated[receiver];
        return updated;
      });
      setSentDecisions(prev => {
        const updated = { ...prev };
        delete updated[receiver];
        return updated;
      });

    } catch (error) {
      console.error('Error sending feedback:', error);
    } finally {
      setProcessingAgent(null);
    }
  };

  useEffect(() => {
    const loadEstablishedRelations = async () => {
      try {
        if (!session?.user?.accessToken) return;
        const response = await fetch(`${API_URL}/api/get_established_relations`, {
          method: 'GET',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${session.user.accessToken}`,
          },
        });
        const data = await response.json();
        console.log(response)
        setEstablishedRelations(data.relations);
      } catch (error) {
        console.error('Failed to load established relations:', error);
      }
    };
    loadEstablishedRelations();
  }, [session]);

  useEffect(() => {
    const loadSentDecisions = async () => {
      try {
        if (!session?.user?.accessToken) return;
        const response = await fetch(`${API_URL}/api/get_agent_sent_decision`, {
          method: 'GET',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${session.user.accessToken}`,
          },
        });
        const data = await response.json();
        setSentDecisions(data.relations);
      } catch (error) {
        console.error('Failed to load sent decisions:', error);
      }
    };
    loadSentDecisions();
  }, [session]);

  useEffect(() => {
    const loadSuggestedAgents = async () => {
      if (status !== 'authenticated' || !session?.user?.accessToken) return;
      try {
        const response = await fetch(`${API_URL}/api/get_pending_relations`, {
          method: 'GET',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${session.user.accessToken}`,
          }
        });
        const data = await response.json();
        setSuggestedAgents(data.relations);
      } catch (error) {
        console.error('Failed to load suggested agents:', error);
      }
    };
    loadSuggestedAgents();
  }, [session, status]);

  async function handleSetup(e: FormEvent) {
    e.preventDefault();
    if (!session?.user?.accessToken) return;
    if (isSubmitting) return;

    setMessage('');


    try {
      setIsSubmitting(true);
      const res = await fetch(`${API_URL}/api/setup`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${session.user.accessToken}`,
        },
        body: JSON.stringify({
          user: session.user.id || session.user.name,
          content: setupContent,
          default_value: strictnessValue
        }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        addMessage(errData.detail || 'Error during setup');
        return;
      }

      addMessage('Setup successful!');
      setSetupContent('');
      await fetchAgentInformation();
    } catch (error) {
      console.error(error);
      setIsSubmitting(false)
      addMessage('Setup request failed.');
    }
  }

  const addMessage = (text: string) => {
    const newMessage = {
      id: Date.now().toString(),
      text,
      visible: true
    };

    setMessages(prev => {
      if (prev.length > 0) {
        const previousMessageId = prev[prev.length - 1].id;
        const timer = timersRef.current[previousMessageId];
        if (timer) {
          clearTimeout(timer);
          delete timersRef.current[previousMessageId];
        }
      }
      return [newMessage];
    });

    timersRef.current[newMessage.id] = setTimeout(() => {
      closeMessage(newMessage.id);
    }, 3000);
  };

  const removeMessage = (id: string) => {
    setMessages(prev => prev.filter(msg => msg.id !== id));
  };

  const closeMessage = (id: string) => {
    setMessages(prev => prev.map(msg =>
      msg.id === id ? {...msg, visible: false} : msg
    ));

    const timer = timersRef.current[id];
    if (timer) {
      clearTimeout(timer);
      delete timersRef.current[id];
    }
  };

  useEffect(() => {
    return () => {
      Object.values(timersRef.current).forEach(clearTimeout);
    };
  }, []);


  function startEditing() {
    if (!info) return;
    setMessage('');

    setEditedPolicies(JSON.stringify(info.policies || [], null, 2));
    setEditedPublic(JSON.stringify(info.public_information || [], null, 2));
    setEditedPrivate(JSON.stringify(info.private_information || [], null, 2));

    setEditing(true);
  }

  function cancelEditing() {
    setEditing(false);
    setMessage('');
    setResetConnections(false);
  }

  async function saveEdits() {
    if (!session?.user?.accessToken) return;

    let parsedPolicies, parsedPublic, parsedPrivate;
    try {
      parsedPolicies = JSON.parse(editedPolicies);
      parsedPublic = JSON.parse(editedPublic);
      parsedPrivate = JSON.parse(editedPrivate);
    } catch (err) {
      addMessage('Error parsing JSON. Please ensure valid JSON format.');
      return;
    }

    const requestBody = {
      user: session.user.id || session.user.name || 'unknown_user',
      policies: parsedPolicies,
      public_information: parsedPublic,
      private_information: parsedPrivate,
      reset: resetConnections ? 1 : 0,
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
        addMessage(errData.detail || 'Error saving changes.');
        return;
      }

      addMessage('Changes saved successfully!');
      setEditing(false);
      setResetConnections(false);
      await fetchAgentInformation();
    } catch (error) {
      console.error(error);
      addMessage('Request to change_information failed.');
    }
  }

  function handleSignOut() {
    signOut();
  }

  if (status === 'loading') {
    return <p>Loading session...</p>;
  }
  if (status === 'unauthenticated') {
    router.push('/auth');
    return null;
  }

  return (
    <div className="p-4 max-w-4xl mx-auto text-black">
      {}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <ProfileDropdown
            onSignOut={handleSignOut}
            username={session?.user?.name ?? "U"}
            info={info}
        />
      </div>

      {messages.map((message) => (
        <div
          key={message.id}
          className={`my-2 p-2 bg-yellow-100 border border-yellow-300 text-yellow-800 rounded flex justify-between items-center transition-opacity duration-300 ${
            message.visible ? 'opacity-100' : 'opacity-0'
          }`}
          onTransitionEnd={() => {
            if (!message.visible) {
              removeMessage(message.id);
            }
          }}
        >
          <span>{message.text}</span>
          <button
            onClick={() => closeMessage(message.id)}
            className="ml-2 text-yellow-700 hover:text-yellow-900 text-lg font-bold"
            aria-label="Close message"
          >
            &times;
          </button>
        </div>
      ))}

      {/* If info not yet fetched, show a placeholder */}
      {!info && <p>Loading agent information...</p>}

      {info && (
        <>
          {!info.isSetup ? (
            <div className="p-4 border rounded bg-gray-100">
              <h2 className="text-lg font-semibold">
                Your agent is not set up yet
              </h2>
              <form onSubmit={handleSetup}>
                <div className="mb-4">
                  <p className="text-sm text-gray-600 mb-3">
                    How strict are you with your connections?
                  </p>
                  <div className="space-y-2">
                    {strictnessOptions.map((option) => (
                      <div key={option.value} className="flex items-start space-x-3">
                        <input
                          type="radio"
                          id={`strictness-${option.value}`}
                          name="connectionStrictness"
                          value={option.value}
                          checked={strictnessValue === option.value}
                          onChange={(e) => setStrictnessValue(Number(e.target.value))}
                          className="mt-1"
                          required
                        />
                        <div className="flex-1">
                          <label htmlFor={`strictness-${option.value}`} className="font-medium">
                            <p className="text-sm text-gray-600">{option.description}</p>
                          </label>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <p className="text-sm text-gray-600 mb-3">
                  Provide some setup content:
                </p>
                <textarea
                  className="w-full p-2 border rounded mb-2"
                  value={setupContent}
                  onChange={(e) => setSetupContent(e.target.value)}
                  placeholder="Enter your setup data..."
                />
                <button
                  type="submit"
                  className={`bg-blue-600 text-white px-4 py-2 rounded ${
                    isSubmitting ? 'opacity-50 cursor-not-allowed' : ''
                  }`}
                  disabled={isSubmitting}
                >
                  {isSubmitting ? (
                    <span className="flex items-center">
                      <svg className="animate-spin h-4 w-4 mr-2" viewBox="0 0 24 24">
                        <path
                          fill="currentColor"
                          d="M12 4V1L8 5l4 4V6c3.31 0 6 2.69 6 6 0 1.01-.25 1.97-.7 2.8l1.46 1.46A7.93 7.93 0 0020 12c0-4.42-3.58-8-8-8zm0 14c-3.31 0-6-2.69-6-6 0-1.01.25-1.97.7-2.8L5.24 7.74A7.93 7.93 0 004 12c0 4.42 3.58 8 8 8v3l4-4-4-4v3z"
                        />
                      </svg>
                      Submitting...
                    </span>
                  ) : (
                    'Complete Setup'
                  )}
                </button>
              </form>
            </div>
          ) : (
            <>
              {/* If all three are null => Setup in progress */}
              {info.policies === null &&
              info.public_information === null &&
              info.private_information === null ? (
                <p className="font-semibold text-orange-700">
                  Setup in progress...
                </p>
              ) : !editing ? (
                  <>
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
                            {info.policies}
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
                            {info.public_information}
                          </ul>
                      ) : (
                          <p className="italic mb-4">No public information</p>
                      )}

                      <h2 className="text-lg font-semibold mb-1">
                        Private Information
                      </h2>
                    {info.private_information && info.private_information.length > 0 ? (
                      <ul className="list-disc list-inside pl-4 mb-4">
                        {info.private_information}
                      </ul>
                    ) : (
                      <p className="italic">No private information</p>
                    )}
                    </div>
                    <div className="border rounded-lg p-4 bg-white shadow-sm mt-4">
                      <h2 className="text-xl font-semibold mb-4 flex items-center">
                        <svg className="w-5 h-5 mr-2 text-green-500" fill="none" stroke="currentColor"
                             viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                                d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"/>
                        </svg>
                        Suggested Connections
                      </h2>
                      {Object.entries(suggestedAgents).length === 0 ? (
                          <p className="text-gray-500 italic">No connection suggestions available</p>
                      ) : (
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            {Object.entries(suggestedAgents).map(([username, publicInfo]) => (
                                <div key={username} className="border rounded p-4 relative">
                                  {/* Processing overlay */}
                                  {processingAgent === username && (
                                      <div
                                          className="absolute inset-0 bg-white bg-opacity-75 flex items-center justify-center">
                                        <div
                                            className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-600"></div>
                                      </div>
                                  )}

                                  <div className="mb-3 border-b pb-2">
                                    <h3 className="font-semibold text-lg flex items-center">
                                      <span className="mr-2">👤</span>
                                      {username}
                                    </h3>
                                  </div>

                                  <div className="mb-4">
                                    <p className="text-sm text-gray-600 mb-1">Public Information:</p>
                                    <p className="text-gray-800 whitespace-pre-wrap">{publicInfo}</p>
                                  </div>

                                  <div className="flex justify-end space-x-2">
                                    <button
                                        onClick={() => handleFeedback(username, 1)}
                                        disabled={processingAgent === username}
                                        className="px-3 py-1.5 text-sm bg-green-100 text-green-800 rounded-md hover:bg-green-200 disabled:opacity-50 disabled:cursor-not-allowed"
                                    >
                                      Accept
                                    </button>
                                    <button
                                        onClick={() => handleFeedback(username, 0)}
                                        disabled={processingAgent === username}
                                        className="px-3 py-1.5 text-sm bg-red-100 text-red-800 rounded-md hover:bg-red-200 disabled:opacity-50 disabled:cursor-not-allowed"
                                    >
                                      Reject
                                    </button>
                                  </div>
                                </div>
                            ))}
                          </div>
                      )}
                    </div>
                    <div className="border rounded-lg p-4 bg-white shadow-sm mt-4">
                      <h2 className="text-xl font-semibold mb-4 flex items-center">
                        <svg
                          className="w-5 h-5 mr-2 text-blue-500"
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M12 4.354a4 4 0 110 5.292M12 12a4 4 0 110 5.292M12 19.646a4 4 0 110-5.292M16 12a4 4 0 110 5.292M8 12a4 4 0 110-5.292"
                          />
                        </svg>
                        Connected Agents
                      </h2>
                      {Object.entries(establishedRelations).length === 0 ? (
                        <p className="text-gray-500 italic">No connected agents available</p>
                      ) : (
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          {Object.entries(establishedRelations).map(([username, publicInfo]) => (
                            <div key={username} className="border rounded p-4">
                              <div className="mb-3 border-b pb-2">
                                <h3 className="font-semibold text-lg flex items-center">
                                  <span className="mr-2">👤</span>
                                  {username}
                                </h3>
                              </div>
                              <div className="mb-4">
                                <p className="text-sm text-gray-600 mb-1">Public Information:</p>
                                <p className="text-gray-800 whitespace-pre-wrap">{publicInfo}</p>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                    <div className="border rounded-lg p-4 bg-white shadow-sm mt-4">
                      <h2 className="text-xl font-semibold mb-4 flex items-center">
                        <svg
                          className="w-5 h-5 mr-2 text-orange-500"
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"
                          />
                        </svg>
                        Sent Connection Requests
                      </h2>
                      {Object.entries(sentDecisions).length === 0 ? (
                        <p className="text-gray-500 italic">No sent connection requests available</p>
                      ) : (
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          {Object.entries(sentDecisions).map(([username, publicInfo]) => (
                            <div key={username} className="border rounded p-4 relative">
                              {/* Processing overlay */}
                              {processingAgent === username && (
                                <div className="absolute inset-0 bg-white bg-opacity-75 flex items-center justify-center">
                                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-600"></div>
                                </div>
                              )}
                              <div className="mb-3 border-b pb-2">
                                <h3 className="font-semibold text-lg flex items-center">
                                  <span className="mr-2">👤</span>
                                  {username}
                                </h3>
                              </div>
                              <div className="mb-4">
                                <p className="text-sm text-gray-600 mb-1">Public Information:</p>
                                <p className="text-gray-800 whitespace-pre-wrap">{publicInfo}</p>
                              </div>
                              <div className="flex justify-end space-x-2">
                                <button
                                  onClick={() => handleFeedback(username, 1)}
                                  disabled={processingAgent === username}
                                  className="px-3 py-1.5 text-sm bg-green-100 text-green-800 rounded-md hover:bg-green-200 disabled:opacity-50 disabled:cursor-not-allowed"
                                >
                                  Accept
                                </button>
                                <button
                                  onClick={() => handleFeedback(username, 0)}
                                  disabled={processingAgent === username}
                                  className="px-3 py-1.5 text-sm bg-red-100 text-red-800 rounded-md hover:bg-red-200 disabled:opacity-50 disabled:cursor-not-allowed"
                                >
                                  Reject
                                </button>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </>
              ) : (
                  <>
                    <div className="border p-4 rounded bg-white">
                      <h2 className="text-lg font-semibold mb-2">
                        Edit Policies
                      </h2>
                      <textarea
                          className="w-full border p-2 rounded h-40 mb-4"
                          value={editedPolicies}
                          onChange={(e) => setEditedPolicies(e.target.value)}/>

                      <h2 className="text-lg font-semibold mb-2">
                        Edit Public Information
                      </h2>
                      <textarea
                          className="w-full border p-2 rounded h-40 mb-4"
                          value={editedPublic}
                          onChange={(e) => setEditedPublic(e.target.value)}/>

                      <h2 className="text-lg font-semibold mb-2">
                        Edit Private Information
                      </h2>
                      <textarea
                          className="w-full border p-2 rounded h-40 mb-4"
                          value={editedPrivate}
                          onChange={(e) => setEditedPrivate(e.target.value)}/>

                      <div className="flex items-center mb-4 space-x-2">
                        <input
                          id="resetConnections"
                          type="checkbox"
                          checked={resetConnections}
                          onChange={() => setResetConnections(prev => !prev)}
                          className="h-4 w-4 border-gray-300 rounded"
                        />
                        <label htmlFor="resetConnections" className="text-sm text-gray-600">
                          Reset existing connections
                        </label>
                      </div>


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

                  </>
              )}
            </>
          )}
        </>
      )}

  </div>

  );
}
