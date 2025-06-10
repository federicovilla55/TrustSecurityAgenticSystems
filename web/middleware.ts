import { withAuth } from 'next-auth/middleware';

// Ensure only authenticated users can use /dashboard or /settings
export default withAuth({
  pages: {
    signIn: '/auth'
  }
});

export const config = {
  matcher: ['/dashboard/:path*', '/settings/:path*']
};
