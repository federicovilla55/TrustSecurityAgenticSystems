// middleware.ts (App Router style)
import { withAuth } from 'next-auth/middleware';

export default withAuth({
  pages: {
    signIn: '/login',
  },
});

// This config ensures that any path matching e.g. /dashboard or /settings
// will require authentication:
export const config = {
  matcher: [
    '/dashboard/:path*',
    '/settings/:path*',
  ],
};
