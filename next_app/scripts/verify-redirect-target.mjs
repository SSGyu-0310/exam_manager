import { normalizeRedirectTarget } from '../src/lib/security/redirect.ts';

const testCases = [
    {
        name: 'allows an internal path',
        raw: '/dashboard',
        fallback: '/fallback',
        expected: '/dashboard',
    },
    {
        name: 'allows internal path with query and hash',
        raw: '/dashboard?tab=mine#top',
        fallback: '/fallback',
        expected: '/dashboard?tab=mine#top',
    },
    {
        name: 'trims whitespace for valid internal path',
        raw: '   /profile   ',
        fallback: '/fallback',
        expected: '/profile',
    },
    {
        name: 'blocks protocol-relative target',
        raw: '//evil.example.com/phish',
        fallback: '/dashboard',
        expected: '/dashboard',
    },
    {
        name: 'blocks http scheme',
        raw: 'http://evil.example.com/phish',
        fallback: '/dashboard',
        expected: '/dashboard',
    },
    {
        name: 'blocks https scheme',
        raw: 'https://evil.example.com/phish',
        fallback: '/dashboard',
        expected: '/dashboard',
    },
    {
        name: 'blocks javascript scheme',
        raw: 'javascript:alert(1)',
        fallback: '/dashboard',
        expected: '/dashboard',
    },
    {
        name: 'blocks data scheme',
        raw: 'data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==',
        fallback: '/dashboard',
        expected: '/dashboard',
    },
    {
        name: 'blocks backslash in path',
        raw: '/\\windows\\path',
        fallback: '/dashboard',
        expected: '/dashboard',
    },
    {
        name: 'blocks empty raw value',
        raw: '',
        fallback: '/dashboard',
        expected: '/dashboard',
    },
    {
        name: 'blocks whitespace raw value',
        raw: '   ',
        fallback: '/dashboard',
        expected: '/dashboard',
    },
    {
        name: 'uses root when fallback itself is unsafe',
        raw: undefined,
        fallback: 'https://evil.example.com/fallback',
        expected: '/',
    },
];

let failed = 0;

for (const { name, raw, fallback, expected } of testCases) {
    const actual = normalizeRedirectTarget(raw, fallback);
    if (actual !== expected) {
        failed += 1;
        console.error(
            `[FAIL] ${name}: expected "${expected}", got "${actual}" (raw=${String(raw)}, fallback=${fallback})`
        );
    }
}

if (failed > 0) {
    console.error(`\n${failed} case(s) failed.`);
    process.exit(1);
}

console.log(`All ${testCases.length} redirect normalization checks passed.`);
