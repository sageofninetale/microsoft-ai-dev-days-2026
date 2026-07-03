import os

ICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512">
    <defs>
        <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="12" result="coloredBlur"/>
            <feMerge>
                <feMergeNode in="coloredBlur"/>
                <feMergeNode in="SourceGraphic"/>
            </feMerge>
        </filter>
        <filter id="outerGlow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="24" result="blur"/>
            <feComponentTransfer in="blur" result="glow">
                <feFuncA type="linear" slope="0.5"/>
            </feComponentTransfer>
            <feMerge>
                <feMergeNode in="glow"/>
                <feMergeNode in="SourceGraphic"/>
            </feMerge>
        </filter>
    </defs>
    
    <!-- Stylized Geometric Nurse Profile (#3D4F2F Forest Green) -->
    <!-- Profile Path -->
    <path d="M 256 100 
             A 140 140 0 0 0 120 240 
             C 120 320, 160 380, 200 440 
             L 320 440 
             L 320 380 
             L 380 340 
             L 350 310 
             L 380 270 
             L 320 230 
             L 300 160 Z" 
          fill="none" stroke="#3D4F2F" stroke-width="20" stroke-linejoin="round" stroke-linecap="round"/>
          
    <!-- Nurse Cap -->
    <path d="M 190 60 L 320 60 L 300 110 L 210 110 Z" fill="none" stroke="#3D4F2F" stroke-width="14" stroke-linejoin="round"/>
    <path d="M 255 75 L 255 95 M 245 85 L 265 85" stroke="#3D4F2F" stroke-width="8" stroke-linecap="round"/>

    <!-- Neural Network inside head (#C5E35C Lime with #E8F5B8 Glow) -->
    <g transform="translate(10, 20)">
        <!-- Core glow background -->
        <circle cx="230" cy="240" r="50" fill="#E8F5B8" filter="url(#outerGlow)" opacity="0.6"/>
        
        <!-- Connections -->
        <g stroke="#C5E35C" stroke-width="8" stroke-linecap="round">
            <line x1="230" y1="200" x2="180" y2="250" />
            <line x1="230" y1="200" x2="280" y2="240" />
            <line x1="180" y1="250" x2="220" y2="300" />
            <line x1="280" y1="240" x2="250" y2="310" />
            <line x1="220" y1="300" x2="250" y2="310" />
        </g>
        
        <!-- Nodes -->
        <g fill="#C5E35C" filter="url(#glow)">
            <circle cx="230" cy="200" r="14" />
            <circle cx="180" cy="250" r="10" />
            <circle cx="280" cy="240" r="12" />
            <circle cx="220" cy="300" r="10" />
            <circle cx="250" cy="310" r="8" />
        </g>
        
        <!-- Dark inner dots for premium feel -->
        <g fill="#3D4F2F">
            <circle cx="230" cy="200" r="4" />
            <circle cx="280" cy="240" r="4" />
            <circle cx="180" cy="250" r="3" />
            <circle cx="220" cy="300" r="3" />
        </g>
    </g>
</svg>
"""

FULL_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 1024" width="1024" height="1024">
    <style>
        .logo-text { font-family: 'Inter', 'Poppins', sans-serif; font-weight: 600; font-size: 110px; fill: #3D4F2F; }
        .tagline { font-family: 'Inter', 'Poppins', sans-serif; font-weight: 500; font-size: 28px; fill: #5A6D4B; letter-spacing: 4px; }
    </style>
    <!-- Background is explicitly transparent by not declaring a rect -->
    
    <!-- Scale icon up and center it horizontally, shift up slightly to make room for text -->
    <g transform="translate(256, 120)">
        {icon_content}
    </g>
    
    <!-- Text Elements -->
    <text x="512" y="800" text-anchor="middle" class="logo-text">CascadeAI</text>
    <text x="512" y="860" text-anchor="middle" class="tagline">INTELLIGENT HEALTHCARE ASSISTANT</text>
</svg>
""".replace('{icon_content}', ICON_SVG.replace('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512">', '').replace('</svg>', ''))

with open('cascade-logo-icon.svg', 'w') as f:
    f.write(ICON_SVG)
    
with open('cascade-logo-full.svg', 'w') as f:
    f.write(FULL_SVG)

print("SVGs generated.")
