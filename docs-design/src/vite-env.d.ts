/// <reference types="vite/client" />

declare global {
  namespace JSX {
    interface IntrinsicElements {
      'model-viewer': React.DetailedHTMLProps<
        React.HTMLAttributes<HTMLElement> & {
          src?: string
          alt?: string
          poster?: string
          'animation-name'?: string
          autoplay?: boolean
          'camera-controls'?: boolean
          'touch-action'?: string
          'auto-rotate'?: boolean
          'shadow-intensity'?: string | number
          'shadow-softness'?: string | number
          'exposure'?: string | number
          'camera-orbit'?: string
          'min-camera-orbit'?: string
          'max-camera-orbit'?: string
          'interaction-prompt'?: string
          loading?: 'auto' | 'lazy' | 'eager'
          reveal?: 'auto' | 'interaction' | 'manual'
        },
        HTMLElement
      >
    }
  }
}
