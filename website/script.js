/* ===================================================================
   CascadeAI — Interactive Features
   =================================================================== */

document.addEventListener('DOMContentLoaded', () => {

    // ===== Scroll Reveal (Spring Physics) =====
    const revealElements = document.querySelectorAll('.scroll-reveal');
    const revealObserver = new IntersectionObserver((entries) => {
        entries.forEach((entry, i) => {
            if (entry.isIntersecting) {
                // Stagger siblings
                const siblings = entry.target.parentElement.querySelectorAll('.scroll-reveal');
                const index = Array.from(siblings).indexOf(entry.target);
                setTimeout(() => {
                    entry.target.classList.add('visible');
                }, index * 100);
                revealObserver.unobserve(entry.target);
            }
        });
    }, { threshold: 0.15, rootMargin: '0px 0px -40px 0px' });

    revealElements.forEach(el => revealObserver.observe(el));

    // ===== Navigation scroll effect =====
    const nav = document.getElementById('nav');

    const onScroll = () => {
        if (window.scrollY > 60) {
            nav.classList.add('scrolled');
        } else {
            nav.classList.remove('scrolled');
        }
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();

    // ===== Mobile hamburger menu =====
    const hamburger = document.getElementById('hamburger');
    const navLinks = document.getElementById('navLinks');

    hamburger.addEventListener('click', () => {
        navLinks.classList.toggle('open');
        hamburger.classList.toggle('active');

        const spans = hamburger.querySelectorAll('span');
        if (hamburger.classList.contains('active')) {
            spans[0].style.transform = 'rotate(45deg) translate(5px, 5px)';
            spans[1].style.opacity = '0';
            spans[2].style.transform = 'rotate(-45deg) translate(5px, -5px)';
        } else {
            spans[0].style.transform = '';
            spans[1].style.opacity = '';
            spans[2].style.transform = '';
        }
    });

    // ===== Pricing toggle =====
    const toggle = document.getElementById('pricingToggle');
    const lblM = document.getElementById('lblMonthly');
    const lblY = document.getElementById('lblYearly');
    const prices = document.querySelectorAll('.price[data-m]');
    let isYearly = false;

    lblM.classList.add('active');

    toggle.addEventListener('click', () => {
        isYearly = !isYearly;
        toggle.classList.toggle('active', isYearly);
        lblM.classList.toggle('active', !isYearly);
        lblY.classList.toggle('active', isYearly);

        prices.forEach(el => {
            const val = isYearly ? el.dataset.y : el.dataset.m;
            el.textContent = val === '0' ? '$0' : `$${val}`;
        });
    });

    // ===== FAQ accordion =====
    document.querySelectorAll('.faq-q').forEach(btn => {
        btn.addEventListener('click', () => {
            const item = btn.parentElement;
            const isOpen = item.classList.contains('open');

            // Close all others
            document.querySelectorAll('.faq-item.open').forEach(openItem => {
                if (openItem !== item) {
                    openItem.classList.remove('open');
                }
            });

            item.classList.toggle('open', !isOpen);
        });
    });

    // ===== Magnetic button hover =====
    document.querySelectorAll('.magnetic').forEach(btn => {
        btn.addEventListener('mousemove', (e) => {
            const rect = btn.getBoundingClientRect();
            const x = e.clientX - rect.left - rect.width / 2;
            const y = e.clientY - rect.top - rect.height / 2;
            btn.style.transform = `translate(${x * 0.15}px, ${y * 0.15}px)`;
        });

        btn.addEventListener('mouseleave', () => {
            btn.style.transform = '';
        });
    });

    // ===== Active nav link highlighting =====
    const sections = document.querySelectorAll('section[id]');
    const navLinksAll = document.querySelectorAll('.nav-link');

    const highlightNav = () => {
        const scrollY = window.scrollY + 120;

        sections.forEach(section => {
            const top = section.offsetTop;
            const bottom = top + section.offsetHeight;
            const id = section.getAttribute('id');

            navLinksAll.forEach(link => {
                if (link.getAttribute('href') === `#${id}`) {
                    if (scrollY >= top && scrollY < bottom) {
                        link.classList.add('active');
                    } else {
                        link.classList.remove('active');
                    }
                }
            });
        });
    };

    window.addEventListener('scroll', highlightNav, { passive: true });

    // ===== Smooth scroll for nav links =====
    document.querySelectorAll('a[href^="#"]').forEach(link => {
        link.addEventListener('click', (e) => {
            const target = document.querySelector(link.getAttribute('href'));
            if (target) {
                e.preventDefault();
                target.scrollIntoView({ behavior: 'smooth', block: 'start' });

                // Close mobile menu
                navLinks.classList.remove('open');
                hamburger.classList.remove('active');
                hamburger.querySelectorAll('span').forEach(s => {
                    s.style.transform = '';
                    s.style.opacity = '';
                });
            }
        });
    });

});
