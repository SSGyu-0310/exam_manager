'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { apiFetch } from '@/lib/http';

interface Template {
    id: number;
    title: string;
    schoolTag?: string;
    gradeTag?: string;
    subjectTag?: string;
    description?: string;
}

export default function TemplatesPage() {
    const [templates, setTemplates] = useState<Template[]>([]);
    const [loading, setLoading] = useState(true);
    const [schoolFilter, setSchoolFilter] = useState('');
    const [gradeFilter, setGradeFilter] = useState('');
    const [subjectFilter, setSubjectFilter] = useState('');

    useEffect(() => {
        fetchTemplates();
    }, [schoolFilter, gradeFilter, subjectFilter]);

    const fetchTemplates = async () => {
        setLoading(true);
        const params = new URLSearchParams();
        if (schoolFilter) params.set('schoolTag', schoolFilter);
        if (gradeFilter) params.set('gradeTag', gradeFilter);
        if (subjectFilter) params.set('subjectTag', subjectFilter);

        try {
            const data = await apiFetch<{ ok: boolean; data: Template[] }>(
                `/api/public/curriculums?${params.toString()}`
            );
            if (data.ok) {
                setTemplates(data.data);
            }
        } catch (error) {
            console.error('Failed to fetch templates', error);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen bg-gray-50 py-8">
            <div className="max-w-6xl mx-auto px-4">
                <h1 className="text-3xl font-bold text-gray-900 mb-2">📚 커리큘럼 템플릿</h1>
                <p className="text-gray-600 mb-8">학교/학년별 예시 커리큘럼을 둘러보고 내 계정으로 복사하세요.</p>

                {/* Filters */}
                <div className="flex flex-wrap gap-4 mb-8">
                    <input
                        type="text"
                        placeholder="학교 (예: 서울과고)"
                        className="px-4 py-2 border rounded-lg focus:ring-2 focus:ring-indigo-500"
                        value={schoolFilter}
                        onChange={(e) => setSchoolFilter(e.target.value)}
                    />
                    <input
                        type="text"
                        placeholder="학년 (예: 고2)"
                        className="px-4 py-2 border rounded-lg focus:ring-2 focus:ring-indigo-500"
                        value={gradeFilter}
                        onChange={(e) => setGradeFilter(e.target.value)}
                    />
                    <input
                        type="text"
                        placeholder="과목 (예: 생명과학)"
                        className="px-4 py-2 border rounded-lg focus:ring-2 focus:ring-indigo-500"
                        value={subjectFilter}
                        onChange={(e) => setSubjectFilter(e.target.value)}
                    />
                </div>

                {/* Template Grid */}
                {loading ? (
                    <div className="text-center py-12 text-gray-500">로딩 중...</div>
                ) : templates.length === 0 ? (
                    <div className="text-center py-12 text-gray-500">
                        등록된 템플릿이 없습니다.
                    </div>
                ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                        {templates.map((template) => (
                            <Link
                                key={template.id}
                                href={`/templates/${template.id}`}
                                className="block bg-white rounded-xl shadow-md hover:shadow-lg transition-shadow p-6"
                            >
                                <h2 className="text-xl font-semibold text-gray-900 mb-2">{template.title}</h2>
                                <div className="flex flex-wrap gap-2 mb-3">
                                    {template.schoolTag && (
                                        <span className="px-2 py-1 bg-blue-100 text-blue-800 text-xs rounded-full">
                                            {template.schoolTag}
                                        </span>
                                    )}
                                    {template.gradeTag && (
                                        <span className="px-2 py-1 bg-green-100 text-green-800 text-xs rounded-full">
                                            {template.gradeTag}
                                        </span>
                                    )}
                                    {template.subjectTag && (
                                        <span className="px-2 py-1 bg-purple-100 text-purple-800 text-xs rounded-full">
                                            {template.subjectTag}
                                        </span>
                                    )}
                                </div>
                                {template.description && (
                                    <p className="text-gray-600 text-sm line-clamp-2">{template.description}</p>
                                )}
                            </Link>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}
