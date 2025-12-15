import { NextResponse } from 'next/server';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

export async function GET(request: Request, { params }: { params: Promise<{ id: string }> }) {
    try {
        const { id } = await params;
        const response = await fetch(`${BACKEND_URL}/clusters/${encodeURIComponent(id)}/plan`);

        if (!response.ok) {
            if (response.status === 404) return NextResponse.json({ error: 'Plan not found' }, { status: 404 });
            const errorText = await response.text();
            return NextResponse.json({ error: errorText }, { status: response.status });
        }

        const data = await response.json();
        return NextResponse.json(data);
    } catch (error) {
        console.error('Error fetching plan:', error);
        return NextResponse.json({ error: 'Failed to fetch plan' }, { status: 500 });
    }
}

export async function POST(request: Request, { params }: { params: Promise<{ id: string }> }) {
    try {
        const { id } = await params;

        const response = await fetch(`${BACKEND_URL}/clusters/${encodeURIComponent(id)}/plan`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });

        if (!response.ok) {
            const errorText = await response.text();
            return NextResponse.json({ error: errorText }, { status: response.status });
        }

        const data = await response.json();
        return NextResponse.json(data);
    } catch (error) {
        console.error('Error generating plan:', error);
        return NextResponse.json({ error: 'Failed to generate plan' }, { status: 500 });
    }
}
