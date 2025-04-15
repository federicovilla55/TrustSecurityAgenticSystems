// types/next-auth.d.ts
import { DefaultSession, DefaultUser } from 'next-auth';
import { JWT } from 'next-auth/jwt';
import NextAuth from 'next-auth';

declare module 'next-auth' {
  interface User extends DefaultUser {
    // Make ID optional, if you don’t have an actual user ID
    id?: string;
    accessToken?: string;
    // Add more fields if needed
  }

  interface Session {
    user: {
      name: string;
      id?: string;
      accessToken?: string;
    } & DefaultSession['user'];
  }
}

declare module 'next-auth/jwt' {
  interface JWT {
    id?: string;
    accessToken?: string;
    name?: string;
  }
}
