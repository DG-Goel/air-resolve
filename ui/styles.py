"""
Styles for AirResolve operations console.

Professional enterprise design with airline operations aesthetic.
"""

def get_custom_css() -> str:
    """Return custom CSS for the operations console."""
    return """
    <style>
    /* Global styles */
    .main {
        background-color: #f5f7fa;
    }
    
    /* Header styles */
    .header-container {
        background: linear-gradient(135deg, #1e3a5f 0%, #2c5282 100%);
        padding: 1.5rem 2rem;
        border-radius: 8px;
        margin-bottom: 1.5rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    .header-title {
        color: #ffffff;
        font-size: 1.8rem;
        font-weight: 600;
        margin: 0;
        padding: 0;
    }
    
    .header-subtitle {
        color: #cbd5e0;
        font-size: 0.9rem;
        margin-top: 0.25rem;
    }
    
    .header-status {
        background: rgba(255, 255, 255, 0.15);
        padding: 0.5rem 1rem;
        border-radius: 20px;
        color: #fff;
        font-size: 0.85rem;
        display: inline-block;
    }
    
    /* Card styles */
    .info-card {
        background: #ffffff;
        padding: 1.25rem;
        border-radius: 8px;
        border: 1px solid #e2e8f0;
        margin-bottom: 1rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    
    .card-header {
        font-size: 0.75rem;
        font-weight: 600;
        color: #4a5568;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 0.75rem;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid #e2e8f0;
    }
    
    /* Status badges */
    .status-badge {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.03em;
    }
    
    .status-authorized {
        background: #c6f6d5;
        color: #22543d;
    }
    
    .status-escalated {
        background: #fed7d7;
        color: #742a2a;
    }
    
    .status-denied {
        background: #fed7d7;
        color: #742a2a;
    }
    
    .status-warning {
        background: #feebc8;
        color: #7c2d12;
    }
    
    .status-processing {
        background: #bee3f8;
        color: #2c5282;
    }
    
    .status-ready {
        background: #c6f6d5;
        color: #22543d;
    }

    .review-resolve-btn button {
        background: linear-gradient(135deg, #1e3a5f 0%, #2c5282 100%) !important;
        color: #ffffff !important;
        font-weight: 700 !important;
        letter-spacing: 0.04em;
        border: none !important;
        padding: 0.65rem 1.25rem !important;
    }
    
    /* Conversation styles */
    .message-customer {
        background: #edf2f7;
        padding: 0.75rem 1rem;
        border-radius: 8px;
        border-left: 3px solid #4299e1;
        margin-bottom: 0.75rem;
    }
    
    .message-agent {
        background: #ffffff;
        padding: 0.75rem 1rem;
        border-radius: 8px;
        border-left: 3px solid #48bb78;
        margin-bottom: 0.75rem;
        border: 1px solid #e2e8f0;
    }
    
    .message-label {
        font-size: 0.7rem;
        font-weight: 600;
        color: #718096;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 0.25rem;
    }
    
    /* Action cards */
    .action-card {
        background: #ffffff;
        padding: 1rem;
        border-radius: 6px;
        border: 1px solid #e2e8f0;
        margin-bottom: 0.75rem;
    }
    
    .action-header {
        font-size: 0.85rem;
        font-weight: 600;
        color: #2d3748;
        margin-bottom: 0.5rem;
    }
    
    .action-detail {
        font-size: 0.8rem;
        color: #718096;
        margin: 0.25rem 0;
    }
    
    /* Decision trace */
    .trace-item {
        padding: 0.5rem 0;
        border-bottom: 1px solid #f7fafc;
    }
    
    .trace-label {
        font-size: 0.75rem;
        font-weight: 600;
        color: #4a5568;
        margin-right: 0.5rem;
    }
    
    .trace-value {
        font-size: 0.8rem;
        color: #2d3748;
    }
    
    /* Audit journal */
    .audit-entry {
        padding: 0.5rem 0;
        border-left: 2px solid #e2e8f0;
        padding-left: 0.75rem;
        margin-bottom: 0.5rem;
    }
    
    .audit-time {
        font-size: 0.7rem;
        color: #a0aec0;
        font-family: monospace;
    }
    
    .audit-event {
        font-size: 0.8rem;
        color: #2d3748;
        font-weight: 500;
    }
    
    /* Pipeline banner */
    .pipeline-banner {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 0.75rem 1rem;
        margin-bottom: 0.5rem;
        text-align: center;
        font-size: 0.85rem;
        font-weight: 600;
        color: #1e3a5f;
    }

    .pipeline-step {
        letter-spacing: 0.04em;
    }

    .pipeline-arrow {
        color: #4299e1;
        margin: 0 0.5rem;
    }

    .simulation-label {
        background: #edf2f7;
        color: #4a5568;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        padding: 0.35rem 0.75rem;
        border-radius: 4px;
        display: inline-block;
        margin-bottom: 1rem;
        border: 1px dashed #cbd5e0;
    }

    /* Requested vs authorized */
    .requested-vs-authorized {
        background: #fff5f5;
        border: 1px solid #feb2b2;
        border-radius: 6px;
        padding: 0.6rem 0.75rem;
        margin: 0.75rem 0;
        font-size: 0.8rem;
        color: #742a2a;
    }

    .section-label {
        font-size: 0.72rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-top: 0.75rem;
        margin-bottom: 0.25rem;
    }

    .requested-label { color: #2b6cb0; }
    .authorized-label { color: #276749; }
    .escalated-label { color: #c53030; }

    .requested-card { border-left: 3px solid #4299e1; }
    .authorized-card { border-left: 3px solid #38a169; }
    .escalated-card { border-left: 3px solid #e53e3e; }
    .denied-card { border-left: 3px solid #ed8936; }
    .return-flight-card { border-left: 3px solid #38a169; background: #f0fff4; }

    /* Policy authority panel */
    .policy-panel {
        background: linear-gradient(135deg, #f7fafc 0%, #edf2f7 100%);
        padding: 1rem;
        border-radius: 6px;
        border: 2px solid #4299e1;
        margin: 1rem 0;
    }
    
    .policy-title {
        font-size: 0.75rem;
        font-weight: 700;
        color: #2c5282;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 0.5rem;
    }
    
    /* Responsive adjustments */
    @media (max-width: 768px) {
        .header-container {
            padding: 1rem;
        }
        
        .header-title {
            font-size: 1.4rem;
        }
    }
    
    /* Utility classes */
    .text-muted {
        color: #718096;
    }
    
    .text-small {
        font-size: 0.8rem;
    }
    
    .mb-1 {
        margin-bottom: 0.5rem;
    }
    
    .mb-2 {
        margin-bottom: 1rem;
    }
    
    /* Streamlit overrides */
    .stButton>button {
        border-radius: 6px;
        font-weight: 500;
    }
    
    .stTextArea>div>div>textarea {
        border-radius: 6px;
    }
    
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
    """


def get_status_color(status: str) -> str:
    """Get color code for status."""
    status_colors = {
        "AUTHORIZED": "#38a169",
        "ESCALATED": "#e53e3e",
        "DENIED": "#e53e3e",
        "PARTIALLY_RESOLVED": "#ed8936",
        "PROCESSING": "#4299e1",
        "READY": "#38a169",
        "ERROR": "#e53e3e",
        "GROUNDING_FAILED": "#e53e3e",
        "POLICY_UNSPECIFIED": "#ed8936",
    }
    return status_colors.get(status.upper(), "#718096")
