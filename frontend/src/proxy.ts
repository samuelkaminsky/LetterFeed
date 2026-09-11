import { NextRequest, NextResponse } from 'next/server';

export function proxy(request: NextRequest) {
  const backendUrl = process.env.LETTERFEED_BACKEND_URL || 'http://backend:8000';

  if (request.nextUrl.pathname.startsWith('/api/')) {
    const url = request.nextUrl.clone();
    const path = url.pathname.replace('/api', '');
    url.href = `${backendUrl}${path}${url.search}`;
    return NextResponse.rewrite(url);
  }

  return NextResponse.next();
}

export const config = {
  matcher: '/api/:path*',
};
