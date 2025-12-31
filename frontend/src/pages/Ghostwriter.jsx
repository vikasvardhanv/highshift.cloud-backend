import { Link } from 'react-router-dom';
import { useState } from 'react';
import { generateContent } from '../services/api';
import { Sparkles, Copy, RefreshCw, Send, Check } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

export default function Ghostwriter() {
    const [topic, setTopic] = useState('');
    const [platform, setPlatform] = useState('twitter');
    const [tone, setTone] = useState('');
    const [result, setResult] = useState(null);
    const [generating, setGenerating] = useState(false);
    const [copied, setCopied] = useState(false);
    const apiKey = localStorage.getItem('social_api_key');

    if (!apiKey) {
        return (
            <div className="flex flex-col items-center justify-center min-h-[60vh] text-center px-4 animate-fade-in">
                <div className="w-24 h-24 bg-primary/10 rounded-full flex items-center justify-center mb-6 border border-primary/20">
                    <Sparkles className="w-10 h-10 text-primary" />
                </div>
                <h2 className="text-3xl font-bold mb-4 bg-clip-text text-transparent bg-gradient-to-r from-primary to-secondary">Unlock AI Ghostwriter</h2>
                <p className="text-gray-400 mb-8 max-w-md mx-auto">Let AI write your next viral post. Connect your accounts to start generating content.</p>
                <Link to="/dashboard" className="px-8 py-3 rounded-full bg-primary hover:bg-primaryHover text-white font-bold shadow-lg shadow-primary/20 transition-all hover:scale-105">
                    Connect Accounts
                </Link>
            </div>
        );
    }

    const handleGenerate = async (e) => {
        e.preventDefault();
        setGenerating(true);
        setResult(null);
        try {
            const data = await generateContent(topic, platform, tone);
            setResult(data);
        } catch (err) {
            alert('Failed to generate content');
        } finally {
            setGenerating(false);
        }
    };

    const copyToClipboard = () => {
        if (!result) return;
        navigator.clipboard.writeText(result.content);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    return (
        <div className="max-w-4xl mx-auto pb-20">
            <div className="text-center mb-10">
                <motion.div
                    initial={{ scale: 0 }} animate={{ scale: 1 }}
                    className="w-16 h-16 bg-gradient-to-br from-purple-500 to-pink-500 rounded-2xl mx-auto flex items-center justify-center mb-4 shadow-xl shadow-purple-500/20"
                >
                    <Sparkles className="w-8 h-8 text-white" />
                </motion.div>
                <h1 className="text-4xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-purple-400 to-pink-400">Ghostwriter AI</h1>
                <p className="text-gray-400 mt-2 max-w-lg mx-auto">Your personal AI social media strategist. It knows your brand voice and writes converting copy.</p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                {/* Input Panel */}
                <motion.div initial={{ x: -20, opacity: 0 }} animate={{ x: 0, opacity: 1 }} className="glass-card p-6 rounded-2xl h-fit">
                    <form onSubmit={handleGenerate} className="space-y-6">
                        <div>
                            <label className="block text-xs font-semibold text-gray-400 mb-2 uppercase tracking-wider">What is this post about?</label>
                            <textarea
                                value={topic}
                                onChange={e => setTopic(e.target.value)}
                                className="w-full h-32 bg-black/20 border border-white/10 rounded-xl p-4 text-white focus:border-purple-500/50 outline-none resize-none transition-all"
                                placeholder="e.g., Announcing our new summer collection with a 20% discount..."
                                required
                            />
                        </div>

                        <div className="grid grid-cols-2 gap-4">
                            <div>
                                <label className="block text-xs font-semibold text-gray-400 mb-2 uppercase tracking-wider">Platform</label>
                                <select
                                    value={platform}
                                    onChange={e => setPlatform(e.target.value)}
                                    className="w-full bg-black/20 border border-white/10 rounded-lg px-3 py-2 text-white outline-none focus:border-purple-500/50 appearance-none"
                                >
                                    <option value="twitter">Twitter / X</option>
                                    <option value="linkedin">LinkedIn</option>
                                    <option value="instagram">Instagram</option>
                                    <option value="facebook">Facebook</option>
                                </select>
                            </div>
                            <div>
                                <label className="block text-xs font-semibold text-gray-400 mb-2 uppercase tracking-wider">Tone (Optional)</label>
                                <input
                                    type="text"
                                    value={tone}
                                    onChange={e => setTone(e.target.value)}
                                    className="w-full bg-black/20 border border-white/10 rounded-lg px-3 py-2 text-white outline-none focus:border-purple-500/50"
                                    placeholder="e.g. Witty"
                                />
                            </div>
                        </div>

                        <button
                            type="submit"
                            disabled={generating || !topic}
                            className="w-full py-4 rounded-xl bg-gradient-to-r from-purple-600 to-pink-600 hover:opacity-90 transition-all font-bold text-white shadow-lg shadow-purple-500/20 flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed group"
                        >
                            {generating ? <RefreshCw className="animate-spin w-5 h-5" /> : <Sparkles className="w-5 h-5 group-hover:scale-110 transition-transform" />}
                            Generate Magic
                        </button>
                    </form>
                </motion.div>

                {/* Output Panel */}
                <motion.div initial={{ x: 20, opacity: 0 }} animate={{ x: 0, opacity: 1 }} className="glass-card p-6 rounded-2xl relative min-h-[400px] flex flex-col">
                    <div className="absolute top-0 right-0 p-4 opacity-10 pointer-events-none">
                        <Sparkles className="w-32 h-32" />
                    </div>

                    <h3 className="text-lg font-bold mb-4 text-gray-300">Generated Content</h3>

                    {result ? (
                        <AnimatePresence>
                            <motion.div
                                initial={{ opacity: 0, scale: 0.9 }}
                                animate={{ opacity: 1, scale: 1 }}
                                className="flex-1 flex flex-col"
                            >
                                <div className="bg-white/5 border border-white/10 rounded-xl p-6 mb-4 flex-1 font-medium text-lg leading-relaxed shadow-inner">
                                    {result.content}
                                </div>
                                <div className="flex items-center justify-between text-sm text-gray-500 px-2">
                                    <span>Model: {result.model}</span>
                                    <button
                                        onClick={copyToClipboard}
                                        className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors font-medium
                                        ${copied ? 'bg-green-500/20 text-green-400' : 'bg-white/10 hover:bg-white/20 text-white'}`}
                                    >
                                        {copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                                        {copied ? 'Copied!' : 'Copy Text'}
                                    </button>
                                </div>
                            </motion.div>
                        </AnimatePresence>
                    ) : (
                        <div className="flex-1 flex flex-col items-center justify-center text-gray-500 text-center p-8 border-2 border-dashed border-white/5 rounded-xl">
                            <Sparkles className="w-12 h-12 mb-4 opacity-20" />
                            <p>Enter a topic and hit generate to see the AI in action.</p>
                        </div>
                    )}
                </motion.div>
            </div>
        </div>
    );
}
