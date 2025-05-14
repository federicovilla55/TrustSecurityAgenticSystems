// app/api/auth/[...nextauth]/route.ts
import NextAuth from 'next-auth';
import CredentialsProvider from 'next-auth/providers/credentials';
import { NextAuthOptions } from 'next-auth';

const backendUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export const authOptions: NextAuthOptions = {
  secret: process.env.NEXTAUTH_SECRET,

  session: {
    strategy: 'jwt',
    maxAge: 60 * 60
  },

  providers: [
    CredentialsProvider({
      name: 'Credentials',
      credentials: {
        username: { label: 'Username', type: 'text' },
        password: { label: 'Password', type: 'password' }
      },
      async authorize(credentials, req) {
        if (!credentials?.username || !credentials?.password) {
          throw new Error('Missing username or password');
        }

        const res = await fetch(`${backendUrl}/api/token`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
          body: new URLSearchParams({
            username: credentials.username,
            password: credentials.password
          })
        });

        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          const errorMsg = errData?.detail || 'Invalid credentials';
          throw new Error(errorMsg);
        }

        const data = await res.json() as { access_token: string; token_type: string };
        if (!data?.access_token) {
          throw new Error('No access token returned');
        }

        return {
          id: credentials.username,
          name: credentials.username,
          accessToken: data.access_token
        };
      }
    })
  ],

  callbacks: {
    async jwt({ token, user }) {
      if (user) {
        token.accessToken = user.accessToken;
        token.id = user.id;
      }
      return token;
    },

    async session({ session, token }) {
      if (token) {
        session.user.accessToken = token.accessToken;
        session.user.id = token.id;
      }
      return session;
    }
  },

  pages: {
    signIn: '/auth'
  }
};

const handler = NextAuth(authOptions);

export { handler as GET, handler as POST };