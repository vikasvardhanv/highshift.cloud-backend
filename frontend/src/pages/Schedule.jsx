import { Link } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { getAccounts, schedulePost, getScheduledPosts, cancelScheduledPost } from '../services/api';
import { Calendar, Clock, Send, Trash2, Check, AlertCircle, Loader2 } from 'lucide-react';
import { motion } from 'framer-motion';

export default function Schedule() {
    const [accounts, setAccounts] = useState([]);
    const [scheduledPosts, setScheduledPosts] = useState([]);
    const [selectedAccounts, setSelectedAccounts] = useState([]);
    const [content, setContent] = useState('');
    const [date, setDate] = useState(''); // YYYY-MM-DD
    const [time, setTime] = useState(''); // HH:MM
    const [submitting, setSubmitting] = useState(false);
    const [message, setMessage] = useState(null);
    const apiKey = localStorage.getItem('social_api_key');

    useEffect(() => {
        if (apiKey) loadData();
    }, [apiKey]);

    if (!apiKey) {
        return (
            <div className="flex flex-col items-center justify-center min-h-[60vh] text-center px-4 animate-fade-in">
                <div className="w-24 h-24 bg-primary/10 rounded-full flex items-center justify-center mb-6 border border-primary/20">
                    <Calendar className="w-10 h-10 text-primary" />
                </div>
                <h2 className="text-3xl font-bold mb-4 bg-clip-text text-transparent bg-gradient-to-r from-primary to-secondary">Unlock Scheduler</h2>
                <p className="text-gray-400 mb-8 max-w-md mx-auto">Plan content in advance and let our auto-poster handle the rest. Connect an account to get started.</p>
                <Link to="/dashboard" className="px-8 py-3 rounded-full bg-primary hover:bg-primaryHover text-white font-bold shadow-lg shadow-primary/20 transition-all hover:scale-105">
                    Connect Accounts
                </Link>
            </div>
        );
    }

    const loadData = async () => {
        const [accData, postsData] = await Promise.all([getAccounts(), getScheduledPosts()]);
        setAccounts(accData.accounts || []);
        setScheduledPosts(postsData || []);
    };

    const handleSchedule = async (e) => {
        e.preventDefault();
        setMessage(null);
        if (selectedAccounts.length === 0) return setMessage({ type: 'error', text: 'Select at least one account' });
        if (!date || !time) return setMessage({ type: 'error', text: 'Select date and time' });

        setSubmitting(true);
        try {
            const scheduledFor = new Date(`${date}T${time}`).toISOString();
            const targetAccounts = accounts.filter(a => selectedAccounts.includes(a.accountId))
                .map(a => ({ platform: a.platform, accountId: a.accountId }));

            await schedulePost(targetAccounts, content, scheduledFor);

            setMessage({ type: 'success', text: 'Post scheduled successfully!' });
            setContent('');
            setSelectedAccounts([]);
            loadData(); // refresh list
        } catch (err) {
            setMessage({ type: 'error', text: err.response?.data?.message || err.message });
        } finally {
            setSubmitting(false);
        }
    };

    const handleCancel = async (id) => {
        if (!confirm('Cancel this post?')) return;
        try {
            await cancelScheduledPost(id);
            loadData();
        } catch (err) {
            alert('Failed to cancel');
        }
    };

    const toggleAccount = (id) => {
        if (selectedAccounts.includes(id)) {
            setSelectedAccounts(selectedAccounts.filter(a => a !== id));
        } else {
            setSelectedAccounts([...selectedAccounts, id]);
        }
    };

    return (
        <div className="max-w-6xl mx-auto grid grid-cols-1 lg:grid-cols-3 gap-8 pb-20">
            {/* Create Schedule Column */}
            <div className="lg:col-span-2 space-y-8">
                <div>
                    <h1 className="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-primary to-secondary">Scheduler</h1>
                    <p className="text-gray-400 mt-2">Plan and queue your content for the future.</p>
                </div>

                <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="glass-card p-6 rounded-2xl">
                    <form onSubmit={handleSchedule} className="space-y-6">
                        {/* Account Selector */}
                        <div>
                            <label className="block text-xs font-semibold text-gray-400 mb-3 uppercase tracking-wider">Select Channels</label>
                            <div className="flex flex-wrap gap-2">
                                {accounts.map(acc => (
                                    <button
                                        type="button"
                                        key={acc.accountId}
                                        onClick={() => toggleAccount(acc.accountId)}
                                        className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-all flex items-center gap-2
                                        ${selectedAccounts.includes(acc.accountId)
                                                ? 'bg-primary text-white border-primary'
                                                : 'bg-white/5 text-gray-400 border-white/10 hover:border-white/20'}`}
                                    >
                                        {selectedAccounts.includes(acc.accountId) && <Check className="w-3 h-3" />}
                                        {acc.displayName}
                                    </button>
                                ))}
                            </div>
                        </div>

                        {/* Content */}
                        <div>
                            <label className="block text-xs font-semibold text-gray-400 mb-3 uppercase tracking-wider">Post Content</label>
                            <textarea
                                value={content}
                                onChange={(e) => setContent(e.target.value)}
                                className="w-full h-40 bg-black/20 border border-white/10 rounded-xl p-4 text-white placeholder-gray-600 focus:outline-none focus:border-primary/50 transition-all resize-none"
                                placeholder="What's happening?"
                                required
                            />
                        </div>

                        {/* Date/Time */}
                        <div className="grid grid-cols-2 gap-4">
                            <div>
                                <label className="block text-xs font-semibold text-gray-400 mb-2 uppercase tracking-wider">Date</label>
                                <div className="relative">
                                    <Calendar className="absolute left-3 top-2.5 w-4 h-4 text-gray-500" />
                                    <input
                                        type="date"
                                        value={date}
                                        onChange={(e) => setDate(e.target.value)}
                                        className="w-full bg-black/20 border border-white/10 rounded-lg pl-10 pr-4 py-2 text-white/80 focus:border-primary/50 outline-none"
                                        min={new Date().toISOString().split('T')[0]}
                                        required
                                    />
                                </div>
                            </div>
                            <div>
                                <label className="block text-xs font-semibold text-gray-400 mb-2 uppercase tracking-wider">Time</label>
                                <div className="relative">
                                    <Clock className="absolute left-3 top-2.5 w-4 h-4 text-gray-500" />
                                    <input
                                        type="time"
                                        value={time}
                                        onChange={(e) => setTime(e.target.value)}
                                        className="w-full bg-black/20 border border-white/10 rounded-lg pl-10 pr-4 py-2 text-white/80 focus:border-primary/50 outline-none"
                                        required
                                    />
                                </div>
                            </div>
                        </div>

                        {/* Status Message */}
                        {message && (
                            <div className={`p-3 rounded-lg flex items-center gap-2 text-sm ${message.type === 'success' ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400'}`}>
                                {message.type === 'success' ? <Check className="w-4 h-4" /> : <AlertCircle className="w-4 h-4" />}
                                {message.text}
                            </div>
                        )}

                        <button
                            type="submit"
                            disabled={submitting}
                            className="w-full py-3 rounded-xl bg-gradient-to-r from-primary to-secondary hover:opacity-90 transition-opacity font-bold flex items-center justify-center gap-2 disabled:opacity-50"
                        >
                            {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                            Schedule Post
                        </button>
                    </form>
                </motion.div>
            </div>

            {/* Upcoming List Column */}
            <div>
                <h3 className="text-lg font-bold mb-6 flex items-center gap-2 text-gray-300">
                    <Clock className="w-5 h-5 text-primary" /> Upcoming Queue
                </h3>
                <div className="space-y-4">
                    {scheduledPosts.length === 0 && <p className="text-gray-500 italic text-sm">No scheduled posts.</p>}
                    {scheduledPosts.map((post, i) => (
                        <motion.div
                            key={post._id}
                            initial={{ opacity: 0, x: 20 }}
                            animate={{ opacity: 1, x: 0 }}
                            transition={{ delay: i * 0.1 }}
                            className="glass-card p-4 rounded-xl border-l-2 border-primary group"
                        >
                            <div className="flex justify-between items-start mb-2">
                                <span className="text-xs font-mono text-gray-400 bg-white/5 px-2 py-1 rounded">
                                    {new Date(post.scheduledFor).toLocaleString()}
                                </span>
                                {post.status === 'pending' && (
                                    <button onClick={() => handleCancel(post._id)} className="text-gray-600 hover:text-red-400 transition-colors">
                                        <Trash2 className="w-4 h-4" />
                                    </button>
                                )}
                            </div>
                            <p className="text-sm text-gray-300 line-clamp-2 mb-3">{post.content}</p>
                            <div className="flex gap-1">
                                {post.accounts.map(a => (
                                    <span key={a.accountId} className="w-2 h-2 rounded-full bg-gray-500" title={a.platform}></span>
                                ))}
                            </div>
                        </motion.div>
                    ))}
                </div>
            </div>
        </div>
    );
}
