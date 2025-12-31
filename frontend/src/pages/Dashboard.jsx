import { useEffect, useState } from 'react';
import { getAccounts, getAuthUrl, postContent, disconnectAccount } from '../services/api';
import {
    Facebook, Twitter, Instagram, Linkedin, Youtube,
    Key, Send, Trash2, Check, Copy, Loader2, AlertCircle, CheckCircle
} from 'lucide-react';

const PLATFORMS = [
    { id: 'twitter', name: 'Twitter / X', icon: Twitter },
    { id: 'facebook', name: 'Facebook', icon: Facebook },
    { id: 'instagram', name: 'Instagram', icon: Instagram },
    { id: 'linkedin', name: 'LinkedIn', icon: Linkedin },
    { id: 'youtube', name: 'YouTube', icon: Youtube },
];

export default function Dashboard() {
    const [accounts, setAccounts] = useState([]);
    const [loading, setLoading] = useState(true);
    const [apiKey] = useState(localStorage.getItem('social_api_key'));
    const [postText, setPostText] = useState('');
    const [posting, setPosting] = useState(false);
    const [selectedAccounts, setSelectedAccounts] = useState([]);
    const [postResult, setPostResult] = useState(null);

    useEffect(() => {
        if (apiKey) {
            loadAccounts();
        } else {
            setLoading(false);
        }
    }, [apiKey]);

    const loadAccounts = async () => {
        try {
            const data = await getAccounts();
            setAccounts(data.accounts || []);
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    const handleConnect = async (platformId) => {
        try {
            // Pass redirect param so backend redirects back to us
            const url = await getAuthUrl(platformId, import.meta.env.VITE_CLIENT_REDIRECT || 'http://localhost:5173/auth/callback');
            window.location.href = url;
        } catch (err) {
            alert('Failed to get auth URL: ' + err.message);
        }
    };

    const handleDisconnect = async (platform, accountId) => {
        try {
            await disconnectAccount(platform, accountId);
            await loadAccounts();
        } catch (err) {
            alert('Failed to disconnect');
        }
    }

    const handlePost = async () => {
        if (!postText) return;
        if (selectedAccounts.length === 0) return alert('Select at least one account');

        setPosting(true);
        setPostResult(null);

        const targetAccounts = accounts.filter(a => selectedAccounts.includes(a.accountId))
            // The backend expects an array of objects for 'accounts' in /post/multi or similar logic
            // Based on backend source, /post/multi expects body: { accounts: [{platform, accountId}], content }
            .map(a => ({ platform: a.platform, accountId: a.accountId }));

        try {
            const res = await postContent(targetAccounts, postText);
            setPostResult({ success: true, data: res });
            setPostText('');
            setSelectedAccounts([]);
        } catch (err) {
            setPostResult({ success: false, error: err.response?.data?.message || err.message });
        } finally {
            setPosting(false);
        }
    };

    const toggleAccountSelection = (id) => {
        if (selectedAccounts.includes(id)) {
            setSelectedAccounts(selectedAccounts.filter(a => a !== id));
        } else {
            setSelectedAccounts([...selectedAccounts, id]);
        }
    };

    const copyKey = () => {
        navigator.clipboard.writeText(apiKey);
        alert('Copied API Key');
    };

    if (!apiKey) {
        return (
            <div className="flex flex-col items-center justify-center min-h-[50vh] text-center px-4">
                <h2 className="text-3xl font-bold mb-6 bg-clip-text text-transparent bg-gradient-to-r from-primary to-secondary">Let's Get Started</h2>
                <p className="text-gray-400 mb-10 max-w-md mx-auto">Connect your first account to generate your API Key and start automating your social media presence.</p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 w-full max-w-lg">
                    {PLATFORMS.map(p => (
                        <button
                            key={p.id}
                            onClick={() => handleConnect(p.id)}
                            className="flex items-center justify-center gap-3 px-6 py-4 rounded-xl glass-card hover:bg-white/10 transition-all font-semibold group"
                        >
                            <p.icon className="w-5 h-5 text-gray-400 group-hover:text-white transition-colors" />
                            <span>Connect {p.name}</span>
                        </button>
                    ))}
                </div>
            </div>
        )
    }

    return (
        <div className="max-w-5xl mx-auto animate-fade-in">
            {/* Header / API Key */}
            <div className="glass-card rounded-2xl p-8 mb-10 overflow-hidden relative border-primary/20">
                <div className="absolute -top-10 -right-10 p-4 opacity-50 blur-3xl">
                    <div className="w-64 h-64 bg-primary/20 rounded-full"></div>
                </div>
                <div className="absolute top-4 right-4 text-white/5">
                    <Key className="w-24 h-24 rotate-12" />
                </div>

                <h2 className="text-2xl font-bold mb-4 relative z-10">Your API Credentials</h2>
                <div className="flex items-center gap-2 bg-black/40 p-4 rounded-lg border border-white/5 max-w-2xl relative z-10">
                    <code className="text-primary font-mono text-sm break-all flex-1">{apiKey}</code>
                    <button onClick={copyKey} className="p-2 hover:bg-white/10 rounded-md transition-colors text-gray-400 hover:text-white" title="Copy Key">
                        <Copy className="w-4 h-4" />
                    </button>
                </div>
                <p className="mt-4 text-sm text-gray-500 relative z-10">
                    Include this as <code className="text-gray-300">X-API-Key</code> header in your requests.
                </p>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                {/* Left Column: Accounts */}
                <div className="lg:col-span-1 space-y-6">
                    <div className="flex items-center justify-between">
                        <h3 className="text-xl font-bold">Connected Accounts</h3>
                    </div>

                    {loading ? <div className="flex justify-center"><Loader2 className="animate-spin text-primary" /></div> : (
                        <div className="space-y-3">
                            {accounts.map(acc => (
                                <div key={acc.accountId} className="glass-card p-4 rounded-lg flex items-center justify-between group hover:border-white/20 transition-all">
                                    <div className="flex items-center gap-3">
                                        <div className={`w-8 h-8 rounded-full flex items-center justify-center bg-white/10 text-white border border-white/10`}>
                                            <span className="text-xs uppercase font-bold">{acc.platform[0]}</span>
                                        </div>
                                        <div className="overflow-hidden">
                                            <div className="font-semibold text-sm truncate w-32">{acc.displayName || acc.username}</div>
                                            <div className="text-xs text-gray-500 capitalize">{acc.platform}</div>
                                        </div>
                                    </div>
                                    <button onClick={() => handleDisconnect(acc.platform, acc.accountId)} className="text-gray-600 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-opacity p-2">
                                        <Trash2 className="w-4 h-4" />
                                    </button>
                                </div>
                            ))}
                            {accounts.length === 0 && <p className="text-gray-500 text-sm italic py-4 text-center border dashed border-white/10 rounded-lg">No accounts linked yet.</p>}
                        </div>
                    )}

                    <div className="pt-6 border-t border-white/5">
                        <h4 className="text-sm font-semibold text-gray-400 mb-4 uppercase tracking-wider text-xs">Link New Account</h4>
                        <div className="grid grid-cols-2 gap-2">
                            {PLATFORMS.map(p => (
                                <button
                                    key={p.id}
                                    onClick={() => handleConnect(p.id)}
                                    className="flex items-center gap-2 px-3 py-2.5 rounded-lg bg-surface hover:bg-surfaceHighlight transition-colors text-xs font-medium border border-white/5 hover:border-primary/30 hover:text-primary"
                                >
                                    <p.icon className="w-3.5 h-3.5" /> {p.name}
                                </button>
                            ))}
                        </div>
                    </div>
                </div>

                {/* Right Column: Post Creator */}
                <div className="lg:col-span-2">
                    <div className="glass-card p-6 rounded-2xl h-full flex flex-col">
                        <h3 className="text-xl font-bold mb-6 flex items-center gap-2 border-b border-white/5 pb-4">
                            <Send className="w-5 h-5 text-primary" /> Create New Post
                        </h3>

                        <div className="mb-6">
                            <label className="block text-xs font-semibold text-gray-400 mb-3 uppercase tracking-wider">Target Channels</label>
                            <div className="flex flex-wrap gap-2">
                                {accounts.map(acc => (
                                    <button
                                        key={acc.accountId}
                                        onClick={() => toggleAccountSelection(acc.accountId)}
                                        className={`px-4 py-2 rounded-full text-sm font-medium border transition-all flex items-center gap-2
                                        ${selectedAccounts.includes(acc.accountId)
                                                ? 'bg-primary text-white border-primary shadow-[0_0_15px_rgba(99,102,241,0.3)]'
                                                : 'bg-white/5 text-gray-400 border-white/10 hover:border-white/20 hover:bg-white/10'}`}
                                    >
                                        {selectedAccounts.includes(acc.accountId) && <Check className="w-3 h-3" />}
                                        {acc.displayName || acc.username}
                                    </button>
                                ))}
                                {accounts.length === 0 && <span className="text-sm text-gray-600 italic">Connect accounts to post</span>}
                            </div>
                        </div>

                        <div className="mb-6 flex-1">
                            <label className="block text-xs font-semibold text-gray-400 mb-3 uppercase tracking-wider">Content</label>
                            <textarea
                                value={postText}
                                onChange={(e) => setPostText(e.target.value)}
                                placeholder="What's on your mind? Type your post content here..."
                                className="w-full h-48 bg-black/20 border border-white/10 rounded-xl p-4 text-white placeholder-gray-600 focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/50 transition-all resize-none"
                            ></textarea>
                        </div>

                        <div className="flex items-center justify-end mt-auto pt-4 border-t border-white/5">
                            <button
                                onClick={handlePost}
                                disabled={posting || !postText || selectedAccounts.length === 0}
                                className="px-8 py-3 rounded-full bg-primary hover:bg-primaryHover disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold transition-all shadow-lg flex items-center gap-2 hover:translate-y-[-1px]"
                            >
                                {posting ? <Loader2 className="animate-spin w-5 h-5" /> : <Send className="w-4 h-4" />}
                                Publish Now
                            </button>
                        </div>

                        {postResult && (
                            <div className={`mt-6 p-4 rounded-xl flex items-start gap-3 border ${postResult.success ? 'bg-green-500/5 border-green-500/20 text-green-400' : 'bg-red-500/5 border-red-500/20 text-red-400'}`}>
                                {postResult.success ? <CheckCircle className="w-5 h-5 mt-0.5 shrink-0" /> : <AlertCircle className="w-5 h-5 mt-0.5 shrink-0" />}
                                <div>
                                    <h4 className="font-bold text-sm">{postResult.success ? 'Published Successfully' : 'Failed to Publish'}</h4>
                                    {postResult.error && <p className="text-xs opacity-80 mt-1">{postResult.error}</p>}
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}
