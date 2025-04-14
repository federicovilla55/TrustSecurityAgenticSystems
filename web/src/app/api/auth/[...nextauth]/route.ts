import NextAuth from 'next-auth';
import CredentialsProvider from 'next-auth/providers/credentials';
import { NextAuthOptions } from 'next-auth';
import { NextResponse } from 'next/server';

const backendUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

/**
 * NextAuth config
 */
export const authOptions: NextAuthOptions = {
  secret: process.env.NEXTAUTH_SECRET, // for signing/encrypting session
  session: {
    // We'll use JWT-based sessions
    strategy: 'jwt',
    maxAge: 60 * 60, // 1 hour
  },
  providers: [
    CredentialsProvider({
      name: 'Credentials',
      credentials: {
        username: { label: 'Username', type: 'text' },
        password: { label: 'Password', type: 'password' },
      },
      async authorize(credentials, req) {
        if (!credentials?.username || !credentials?.password) {
          throw new Error('Missing username or password');
        }

        // Call FastAPI's /api/token
        try {
          const response = await fetch(`${backendUrl}/api/token`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: new URLSearchParams({
              username: credentials.username,
              password: credentials.password,
            }),
          });

          if (!response.ok) {
            // e.g. 401
            const errData = await response.json();
            throw new Error(errData.detail || 'Invalid credentials');
          }

          const data = await response.json() as { access_token: string; token_type: string };
          if (!data.access_token) {
            throw new Error('No token returned from backend');
          }

          // Return a user object that includes the token
          return {
            name: credentials.username, // we'll store the username in the `name` field
            accessToken: data.access_token,
          };
        } catch (err: any) {
          throw new Error(err.message || 'Login request failed');
        }
      },
    }),
  ],
  // We store the JWT in the "token" param
  callbacks: {
    // Add the accessToken to the JWT
    async jwt({ token, user }) {
      // On initial login, "user" param is populated
      if (user?.accessToken) {
        token.accessToken = user.accessToken;
        token.username = user.name; // store the username
      }
      return token;
    },
    // Make the token info available in the session
    async session({ session, token }) {
      if (token?.accessToken) {
        // @ts-ignore
        session.user.accessToken = token.accessToken as string;
      }
      if (token?.username) {
        // @ts-ignore
        session.user.name = token.username as string;
      }
      return session;
    },
  },
  // Optionally, customize pages (login, etc.)
  pages: {
    signIn: '/login', // Our custom login route
  },
};

const handler = NextAuth(authOptions);

export { handler as GET, handler as POST };
