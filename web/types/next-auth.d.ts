// types/next-auth.d.ts
import { DefaultSession, DefaultUser } from 'next-auth';
import { JWT } from 'next-auth/jwt';
import NextAuth from 'next-auth';

// Interface for user authentication.
declare module 'next-auth' {
  // User profile is identified by its ID and access token
  interface User extends DefaultUser {
    id?: string;
    accessToken?: string;
  }

  // Data structure identifying the session
  interface Session {
    user: {
      name: string;
      id?: string;
      accessToken?: string;
    } & DefaultSession['user'];
  }
}

declare module 'next-auth/jwt' {
  // Data structure identifying the JWT.
  interface JWT {
    id?: string;
    accessToken?: string;
    name?: string;
  }
}
