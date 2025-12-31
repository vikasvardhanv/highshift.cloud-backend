import { History, CheckCircle, AlertCircle, Clock } from 'lucide-react';

export default function ActivityHistory() {
    // Mock Data
    const history = [
        { id: 1, type: 'post_success', message: 'Published to Twitter', time: '2 mins ago', success: true },
        { id: 2, type: 'post_success', message: 'Published to LinkedIn', time: '2 mins ago', success: true },
        { id: 3, type: 'schedule', message: 'Scheduled post for Aug 24', time: '1 hour ago', success: true },
        { id: 4, type: 'generation', message: 'Generated AI content', time: '3 hours ago', success: true },
        { id: 5, type: 'error', message: 'Failed to connect Instagram: Token Expired', time: '5 hours ago', success: false },
    ];

    return (
        <div className="max-w-4xl mx-auto pb-20">
            <h1 className="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-primary to-secondary mb-2">Activity History</h1>
            <p className="text-gray-400 mb-10">Recent actions and system logs.</p>

            <div className="glass-card rounded-2xl overflow-hidden">
                {history.map((item, i) => (
                    <div key={item.id} className="p-4 border-b border-white/5 flex items-center gap-4 hover:bg-white/5 transition-colors last:border-0">
                        <div className={`w-10 h-10 rounded-full flex items-center justify-center shrink-0 ${item.success ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400'}`}>
                            {item.success ? <CheckCircle className="w-5 h-5" /> : <AlertCircle className="w-5 h-5" />}
                        </div>
                        <div className="flex-1">
                            <h4 className="font-semibold text-sm text-gray-200">{item.message}</h4>
                            <div className="flex items-center gap-1 text-xs text-gray-500 mt-0.5">
                                <Clock className="w-3 h-3" /> {item.time}
                            </div>
                        </div>
                        <div className="text-xs font-mono px-2 py-1 rounded bg-white/5 text-gray-400 border border-white/5 uppercase">
                            {item.type}
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}
