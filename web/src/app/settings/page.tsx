'use client';

import React, {useEffect, useRef, useState} from 'react';
import {signOut, useSession} from 'next-auth/react';
import {useRouter} from 'next/navigation';

interface AgentInformation {
  policies: Array<{ rule_ID: string; content: string }> | null;
  public_information: Array<{ info_ID: string; content: string }> | null;
  private_information: Array<{ [key: string]: any }> | null;
  isSetup: boolean;
  paused: boolean;
  username: string;
}

interface MessageType {
  id: string;
  text: string;
  visible: boolean;
}

interface SettingMenuProperties {
  onSignOut: () => void;
  username: string;
  info: AgentInformation | null;
}


const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const ProfileDropdown = ({ onSignOut, username, info }: SettingMenuProperties) => {
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const userInitial = username?.charAt(0)?.toUpperCase() || 'U';
  const router = useRouter();

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
                router.push('/dashboard');
                setIsDropdownOpen(false);
              }}
              className="block px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 w-full text-left"
              role="menuitem"
            >
              Dashboard
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


export default function SettingsPage() {
  const { data: session, status } = useSession();
  const router = useRouter();

  const [info, setInfo] = useState<AgentInformation | null>(null);
  const [messages, setMessages] = useState<MessageType[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const [editedPolicies, setEditedPolicies] = useState('');
  const [editedPublic, setEditedPublic] = useState('');
  const timersRef = useRef<Record<string, NodeJS.Timeout>>({});
  const [editedPrivate, setEditedPrivate] = useState('');

  useEffect(() => {
    if (status ==='loading') return;
    if (status === 'unauthenticated') {
      router.push('/auth');
      return;
    }

    fetchAgentInformation();
  }, [status]);

  useEffect(() => {
    if (status === 'unauthenticated') {
      router.push('/auth');
    }
    fetchAgentInformation();
  }, [status]);

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

  async function fetchAgentInformation() {
    if (!session?.user?.accessToken) return;

    try {
      const res = await fetch(`${API_URL}/api/get_information`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${session.user.accessToken}`,
        },
        body: JSON.stringify({ type: 7 }),
      });

      if (!res.ok) throw new Error('Failed to fetch info');

      const data: AgentInformation = await res.json();

      console.log("DATA: ", data);

      setInfo({
        policies: data.policies,
        public_information: data.public_information,
        private_information: data.private_information,
        username: data.username,
        paused: data.paused,
        isSetup: data.isSetup
      });

      setEditedPolicies(JSON.stringify(data.policies || [], null, 2));
      setEditedPublic(JSON.stringify(data.public_information || [], null, 2));
      setEditedPrivate(JSON.stringify(data.private_information || [], null, 2));
    } catch (error) {
      addMessage('Failed to fetch agent information');
    }
  }

  async function handleAgentAction(endpoint: string) {
    if (!session?.user?.accessToken) return;

    console.log(endpoint)
    setIsSubmitting(true);
    try {
      const response = await fetch(`${API_URL}/api/${endpoint}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${session.user.accessToken}`,
        },
      });


      if (!response.ok) throw new Error(await response.text());

      await fetchAgentInformation();

      addMessage(`${endpoint} operation successful`);

      if (endpoint === 'delete') {
        router.push('/dashboard');
      }
    } catch (error) {
      addMessage(`Error during ${endpoint} operation`);
    } finally {
      setIsSubmitting(false);
    }
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

    try {
      const res = await fetch(`${API_URL}/api/change_information`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${session.user.accessToken}`,
        },
        body: JSON.stringify({
          user: session.user.id || session.user.name,
          policies: parsedPolicies,
          public_information: parsedPublic,
          private_information: parsedPrivate,
        }),
      });

      if (!res.ok) throw new Error(await res.text());

      addMessage('Changes saved successfully');
      await fetchAgentInformation();
    } catch (error) {
      addMessage('Failed to save changes');
    }
  }

  console.log(info)

  if (!info) return <p>Loading...</p>;

  return (
    <div className="p-4 max-w-4xl mx-auto text-black">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Agent Settings</h1>
        <ProfileDropdown
          onSignOut={() => signOut()}
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

      <div className="space-y-6">
        <div className="border p-4 rounded bg-white">
          <h2 className="text-lg font-semibold mb-4">Agent Controls</h2>
          <div className="flex gap-4">
            {info.paused ? (
              <button
                onClick={() => handleAgentAction('resume')}
                disabled={isSubmitting}
                className="bg-green-600 text-white px-4 py-2 rounded disabled:opacity-50"
              >
                Resume Agent
              </button>
            ) : (
              <button
                onClick={() => handleAgentAction('pause')}
                disabled={isSubmitting}
                className="bg-yellow-600 text-white px-4 py-2 rounded disabled:opacity-50"
              >
                Pause Agent
              </button>
            )}
            <button
              onClick={() => handleAgentAction('delete')}
              disabled={isSubmitting}
              className="bg-red-600 text-white px-4 py-2 rounded disabled:opacity-50"
            >
              Delete Agent
            </button>
          </div>
        </div>

        <div className="border p-4 rounded bg-white">
          <h2 className="text-lg font-semibold mb-4">Edit Policies</h2>
          <textarea
            className="w-full border p-2 rounded h-40 mb-4 font-mono text-sm"
            value={editedPolicies}
            onChange={(e) => setEditedPolicies(e.target.value)}
          />

          <h2 className="text-lg font-semibold mb-4">Edit Public Information</h2>
          <textarea
            className="w-full border p-2 rounded h-40 mb-4 font-mono text-sm"
            value={editedPublic}
            onChange={(e) => setEditedPublic(e.target.value)}
          />

          <h2 className="text-lg font-semibold mb-4">Edit Private Information</h2>
          <textarea
            className="w-full border p-2 rounded h-40 mb-4 font-mono text-sm"
            value={editedPrivate}
            onChange={(e) => setEditedPrivate(e.target.value)}
          />

          <button
            onClick={saveEdits}
            disabled={isSubmitting}
            className="bg-blue-600 text-white px-4 py-2 rounded disabled:opacity-50"
          >
            Save All Changes
          </button>
        </div>
      </div>
    </div>
  );
}