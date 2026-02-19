import { useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useHealStore } from '../stores/useHealStore';

export const AuthCallback = () => {
    const [searchParams] = useSearchParams();
    const navigate = useNavigate();
    const setUser = useHealStore((s) => s.setUser);

    useEffect(() => {
        const login = searchParams.get('login');
        const name = searchParams.get('name');
        const avatar_url = searchParams.get('avatar_url');
        const github_id = searchParams.get('github_id');

        if (login) {
            setUser({
                login,
                name: name || login,
                avatar_url: avatar_url || '',
                github_id: github_id || '',
            });
            navigate('/dashboard', { replace: true });
        } else {
            // OAuth failed — go back to login
            navigate('/', { replace: true });
        }
    }, [searchParams, navigate, setUser]);

    return (
        <div className="min-h-screen bg-[#050505] flex items-center justify-center">
            <div className="flex flex-col items-center gap-4">
                <div className="w-8 h-8 border-2 border-[#00ff9d] border-t-transparent rounded-full animate-spin" />
                <p className="text-sm text-slate-400 font-mono">Authenticating...</p>
            </div>
        </div>
    );
};
