'use client';

import { useEffect, useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { useAuth } from '@/context/AuthContext';
import { apiFetch } from '@/lib/http';

interface Block {
    name: string;
    description?: string;
    lectures: { title: string; order: number }[];
}

interface TemplateDetail {
    id: number;
    title: string;
    schoolTag?: string;
    gradeTag?: string;
    subjectTag?: string;
    description?: string;
    payload: {
        blocks?: Block[];
    };
}

export default function TemplateDetailPage() {
    const params = useParams();
    const router = useRouter();
    const { isAuthenticated, isLoading: authLoading } = useAuth();

    const [template, setTemplate] = useState<TemplateDetail | null>(null);
    const [loading, setLoading] = useState(true);
    const [cloning, setCloning] = useState(false);
    const [error, setError] = useState('');

    const templateId = params.id as string;

    useEffect(() => {
        fetchTemplate();
    }, [templateId]);

    const fetchTemplate = async () => {
        try {
            const data = await apiFetch<{ ok: boolean; data: TemplateDetail }>(
                `/api/public/curriculums/${templateId}`
            );
            if (data.ok) {
                setTemplate(data.data);
            } else {
                setError('템플릿을 찾을 수 없습니다.');
            }
        } catch (err) {
            setError('템플릿을 불러오는 중 오류가 발생했습니다.');
        } finally {
            setLoading(false);
        }
    };

    const handleClone = async () => {
        if (!isAuthenticated) {
            router.push('/login');
            return;
        }

        setCloning(true);
        setError('');

        try {
            const data = await apiFetch<{ ok: boolean; data?: { blockIds?: number[] }; message?: string }>(
                `/api/public/curriculums/${templateId}/clone`,
                { method: 'POST' }
            );

            if (data.ok) {
                const firstBlockId = data.data?.blockIds?.[0];
                if (firstBlockId) {
                    router.push(`/manage/blocks/${firstBlockId}`);
                } else {
                    router.push('/manage');
                }
            } else {
                setError(data.message || '복사에 실패했습니다.');
            }
        } catch (err) {
            setError('복사 중 오류가 발생했습니다.');
        } finally {
            setCloning(false);
        }
    };

    if (loading) {
        return (
            <div className="min-h-screen bg-gray-50 flex items-center justify-center">
                <div className="text-gray-500">로딩 중...</div>
            </div>
        );
    }

    if (error && !template) {
        return (
            <div className="min-h-screen bg-gray-50 flex items-center justify-center">
                <div className="text-center">
                    <div className="text-red-500 mb-4">{error}</div>
                    <button
                        onClick={() => router.push('/templates')}
                        className="text-indigo-600 hover:underline"
                    >
                        ← 템플릿 목록으로
                    </button>
                </div>
            </div>
        );
    }

    if (!template) return null;

    return (
        <div className="min-h-screen bg-gray-50 py-8">
            <div className="max-w-4xl mx-auto px-4">
                {/* Header */}
                <div className="mb-8">
                    <button
                        onClick={() => router.push('/templates')}
                        className="text-gray-600 hover:text-gray-900 mb-4 inline-flex items-center"
                    >
                        ← 템플릿 목록
                    </button>
                    <h1 className="text-3xl font-bold text-gray-900 mb-2">{template.title}</h1>
                    <div className="flex flex-wrap gap-2 mb-4">
                        {template.schoolTag && (
                            <span className="px-3 py-1 bg-blue-100 text-blue-800 text-sm rounded-full">
                                {template.schoolTag}
                            </span>
                        )}
                        {template.gradeTag && (
                            <span className="px-3 py-1 bg-green-100 text-green-800 text-sm rounded-full">
                                {template.gradeTag}
                            </span>
                        )}
                        {template.subjectTag && (
                            <span className="px-3 py-1 bg-purple-100 text-purple-800 text-sm rounded-full">
                                {template.subjectTag}
                            </span>
                        )}
                    </div>
                    {template.description && (
                        <p className="text-gray-600">{template.description}</p>
                    )}
                </div>

                {/* Clone Button */}
                <div className="bg-white rounded-xl shadow-md p-6 mb-8">
                    <div className="flex items-center justify-between">
                        <div>
                            <h2 className="text-lg font-semibold text-gray-900">
                                내 커리큘럼으로 가져오기
                            </h2>
                            <p className="text-gray-600 text-sm">
                                이 템플릿을 복사하여 나만의 커리큘럼으로 사용하세요.
                            </p>
                        </div>
                        <button
                            onClick={handleClone}
                            disabled={cloning || authLoading}
                            className="px-6 py-3 bg-indigo-600 text-white font-semibold rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                        >
                            {cloning ? '복사 중...' : isAuthenticated ? '복사하기' : '로그인 후 복사'}
                        </button>
                    </div>
                    {error && <div className="mt-4 text-red-500 text-sm">{error}</div>}
                </div>

                {/* Content Preview */}
                <div className="bg-white rounded-xl shadow-md p-6">
                    <h2 className="text-xl font-semibold text-gray-900 mb-4">📋 구성 내용</h2>
                    {template.payload?.blocks?.length ? (
                        <div className="space-y-6">
                            {template.payload.blocks.map((block, idx) => (
                                <div key={idx} className="border-l-4 border-indigo-500 pl-4">
                                    <h3 className="text-lg font-medium text-gray-900 mb-2">{block.name}</h3>
                                    {block.description && (
                                        <p className="text-gray-600 text-sm mb-2">{block.description}</p>
                                    )}
                                    {block.lectures?.length > 0 && (
                                        <ul className="space-y-1">
                                            {block.lectures.map((lec, lecIdx) => (
                                                <li key={lecIdx} className="text-gray-700 text-sm flex items-center">
                                                    <span className="w-6 h-6 bg-gray-100 rounded-full flex items-center justify-center text-xs mr-2">
                                                        {lec.order || lecIdx + 1}
                                                    </span>
                                                    {lec.title}
                                                </li>
                                            ))}
                                        </ul>
                                    )}
                                </div>
                            ))}
                        </div>
                    ) : (
                        <p className="text-gray-500">구성 내용이 없습니다.</p>
                    )}
                </div>
            </div>
        </div>
    );
}
