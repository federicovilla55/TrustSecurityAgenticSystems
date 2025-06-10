import NextAuth from 'next-auth';
import CredentialsProvider from 'next-auth/providers/credentials';
import { NextAuthOptions } from 'next-auth';

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const TOKEN_ENDPOINT = `${BACKEND_URL}/api/token`;
const SESSION_MAX_AGE = 60 * 60; // token duration in number of seconds

// NextAuth configuration object
export const authOptions: NextAuthOptions = {
  // Secret for creating tokens
  secret: process.env.NEXTAUTH_SECRET,

  // Session configuration using JSON Web Token
  session: {
    strategy: 'jwt',
    maxAge: SESSION_MAX_AGE
  },

  // Configuration for authentication providers
  providers: [
    // Authentication providers configuration
    CredentialsProvider({
      name: 'Credentials', // Providers Name
      credentials: { // Credential fields
        username: { label: 'Username', type: 'text' },
        password: { label: 'Password', type: 'password' }
      },
      // Authorization function to validate credentials
      async authorize(credentials, req) {
        if (!credentials?.username || !credentials?.password) {
          throw new Error('Missing username or password');
        }

        // Send request to backend API for credential validation
        const res = await fetch(`${TOKEN_ENDPOINT}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
          body: new URLSearchParams({
            username: credentials.username,
            password: credentials.password
          })
        });

        if (!res.ok) {
          // Parse errors if requests fails
          const errData = await res.json().catch(() => ({}));
          const errorMsg = errData?.detail || 'Invalid credentials';
          throw new Error(errorMsg);
        }

        // Parse correct answer
        const data = await res.json() as { access_token: string; token_type: string };
        if (!data?.access_token) {
          throw new Error('No access token returned');
        }

        // Return user object that will be encoded in the JWT
        return {
          id: credentials.username,
          name: credentials.username,
          accessToken: data.access_token
        };
      }
    })
  ],

  callbacks: {
    // When JWT is created/updated, add access token to the JWT.
    async jwt({ token, user }) {
      if (user) {
        token.accessToken = user.accessToken;
        token.id = user.id;
      }
      return token;
    },

    // When a session object is accessed
    async session({ session, token }) {
      if (token) {
        session.user.accessToken = token.accessToken;
        session.user.id = token.id;
      }
      return session;
    }
  },

  // Sign In page configuration and redirect
  pages: {
    signIn: '/auth'
  }
};

// NextAuth handler
const handler = NextAuth(authOptions);

// Export the handler as both GET and POST requets.
export { handler as GET, handler as POST };