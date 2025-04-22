// middleware.ts
import { withAuth } from 'next-auth/middleware';

// This ensures only authenticated users can visit /dashboard or /settings
export default withAuth({
  pages: {
    signIn: '/auth'
  }
});

export const config = {
  matcher: ['/dashboard/:path*', '/settings/:path*']
};
