/**
 * types/next-auth.d.ts
 */
import { DefaultSession, DefaultUser } from 'next-auth';
import { JWT } from 'next-auth/jwt';

// 1) Augment the `User` type to include `accessToken` (and `id` if needed).
declare module 'next-auth' {
  // Returned by `useSession`, `getSession` etc.
  interface Session {
    user: {
      /** You can add any other properties you need here. */
      name?: string | null;
      email?: string | null;
      image?: string | null;
      accessToken?: string;
      id?: string;
    } & DefaultSession['user'];
  }

  interface User extends DefaultUser {
    /** accessToken we receive from FastAPI */
    accessToken?: string;
    id?: string;
  }
}

// 2) Augment the `JWT` interface to include `accessToken`
declare module 'next-auth/jwt' {
  interface JWT {
    /** accessToken to forward to our backend */
    accessToken?: string;
    id?: string;
  }
}
