import { useLayoutEffect, useRef } from 'react';
import { animate, motion, useMotionValue, useTransform } from 'framer-motion';

const edgeMotion = { type: 'tween', duration: 0.3, ease: 'easeOut' };
const trailingDelay = 0.03;

export default function SidebarHighlight({ activeIndex, itemHeight, itemGap, reduceMotion }) {
  const targetTop = activeIndex * (itemHeight + itemGap);
  const targetBottom = targetTop + itemHeight;
  const previousIndex = useRef(activeIndex);
  const top = useMotionValue(targetTop);
  const bottom = useMotionValue(targetBottom);

  // Keep the visible edges ordered if a new navigation interrupts the stretch.
  const visibleTop = useTransform(() => Math.min(top.get(), bottom.get() - itemHeight));
  const visibleHeight = useTransform(() => Math.max(itemHeight, bottom.get() - top.get()));

  useLayoutEffect(() => {
    const previous = previousIndex.current;
    previousIndex.current = activeIndex;
    if (reduceMotion || previous === activeIndex) {
      top.jump(targetTop);
      bottom.jump(targetBottom);
      return;
    }

    const movingDown = activeIndex > previous;
    const topAnimation = animate(top, targetTop, { ...edgeMotion, delay: movingDown ? trailingDelay : 0 });
    const bottomAnimation = animate(bottom, targetBottom, { ...edgeMotion, delay: movingDown ? 0 : trailingDelay });
    return () => {
      topAnimation.stop();
      bottomAnimation.stop();
    };
  }, [activeIndex, bottom, reduceMotion, targetBottom, targetTop, top]);

  if (reduceMotion) {
    return <div className="sidebar-active-pill" style={{ top: targetTop, height: itemHeight }} aria-hidden="true" />;
  }
  return <motion.div className="sidebar-active-pill" style={{ top: visibleTop, height: visibleHeight }} aria-hidden="true" />;
}
