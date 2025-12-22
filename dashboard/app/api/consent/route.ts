import { NextResponse } from 'next/server';
import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';
import { prisma } from '@/lib/prisma';

export async function POST(req: Request) {
  try {
    const session = await getServerSession(authOptions);

    if (!session?.user?.id) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    const body = await req.json();
    const { consented } = body;

    if (typeof consented !== 'boolean') {
      return NextResponse.json({ error: 'Invalid request' }, { status: 400 });
    }

    // Update user consent
    await prisma.user.update({
      where: { id: session.user.id },
      data: {
        consentedToResearch: consented,
        consentedAt: consented ? new Date() : null,
      },
    });

    return NextResponse.json({ success: true });
  } catch (error) {
    console.error('Error updating consent:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}

export async function GET() {
  try {
    const session = await getServerSession(authOptions);

    if (!session?.user?.id) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    const user = await prisma.user.findUnique({
      where: { id: session.user.id },
      select: { consentedToResearch: true, consentedAt: true },
    });

    return NextResponse.json({
      consented: user?.consentedToResearch || false,
      consentedAt: user?.consentedAt,
    });
  } catch (error) {
    console.error('Error fetching consent:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}
