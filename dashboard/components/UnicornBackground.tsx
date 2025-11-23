'use client';

import { useEffect } from 'react';

declare global {
    interface Window {
        UnicornStudio: {
            isInitialized: boolean;
            init?: () => void;
        };
    }
}

export default function UnicornBackground() {
    useEffect(() => {
        if (typeof window === 'undefined') return;

        if (!window.UnicornStudio) {
            window.UnicornStudio = { isInitialized: false };
        }

        const script = document.createElement('script');
        script.src = 'https://cdn.jsdelivr.net/gh/hiunicornstudio/unicornstudio.js@v1.4.29/dist/unicornStudio.umd.js';
        script.onload = () => {
            if (!window.UnicornStudio.isInitialized && window.UnicornStudio.init) {
                window.UnicornStudio.init();
                window.UnicornStudio.isInitialized = true;
            }
        };

        document.body.appendChild(script);

        return () => {
            // Cleanup if necessary, though usually background scripts persist
            if (document.body.contains(script)) {
                document.body.removeChild(script);
            }
        };
    }, []);

    return (
        <div className="fixed top-0 left-0 w-full h-full -z-10 pointer-events-none overflow-hidden">
            <div
                data-us-project="EET25BiXxR2StNXZvAzF"
                className="absolute w-full h-full left-0 top-0"
                style={{ opacity: 0.6 }} // Slight transparency to blend with black bg
            ></div>
            {/* Overlay gradient to ensure text readability */}
            <div className="absolute inset-0 bg-gradient-to-b from-matrix-black/80 via-matrix-black/50 to-matrix-black/80"></div>
        </div>
    );
}
