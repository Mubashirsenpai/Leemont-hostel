document.addEventListener('DOMContentLoaded', function() {
    // Mobile Menu Toggle
    const menuToggle = document.querySelector('.menu-toggle');
    const navLinks = document.querySelector('.nav-links');
    
    if (menuToggle && navLinks) {
        menuToggle.addEventListener('click', () => {
            navLinks.classList.toggle('active');
            menuToggle.classList.toggle('active');
        });
    }
    
    // Close mobile menu when clicking a link
    document.querySelectorAll('.nav-links ul li a').forEach(link => {
        link.addEventListener('click', () => {
            if (navLinks.classList.contains('active')) {
                navLinks.classList.remove('active');
                menuToggle.classList.remove('active');
            }
        });
    });
    
    // Sticky Header and Back to Top Button
    const header = document.querySelector('header');
    const backToTop = document.querySelector('.back-to-top');

    if (header || backToTop) {
        window.addEventListener('scroll', () => {
            if (header) {
                header.classList.toggle('scrolled', window.scrollY > 50);
            }
            if (backToTop) {
                backToTop.classList.toggle('active', window.scrollY > 300);
            }
        });
    }

    // Smooth scrolling for anchor links (if any are added later)
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            // Only prevent default if it's an internal anchor link
            const targetId = this.getAttribute('href');
            if (targetId.length > 1 && targetId.startsWith('#')) { // Ensure it's not just '#'
                const targetElement = document.querySelector(targetId);
                if (targetElement) {
                    e.preventDefault(); // Prevent default only if target exists
                    window.scrollTo({
                        top: targetElement.offsetTop - (header ? header.offsetHeight : 0), // Adjust for fixed header height
                        behavior: 'smooth'
                    });
                }
            }
        });
    });

    // Flash message auto-hide (CSS handles fadeOut, but this ensures removal)
    const flashMessages = document.querySelector('.flash-messages');
    if (flashMessages) {
        // Remove the flash message element from the DOM after its animation
        flashMessages.addEventListener('animationend', (event) => {
            if (event.animationName === 'fadeOut') {
                flashMessages.remove();
            }
        });
    }

    // --- Image Carousel Logic for Hero Section ---
    const slideImages = document.querySelectorAll('.hero-image-slider .slide-image');
    let currentSlide = 0;
    const slideIntervalTime = 5000; // 5 seconds

    function showSlide(index) {
        // Hide all slides
        slideImages.forEach(img => img.classList.remove('active'));
        // Show the current slide
        if (slideImages[index]) {
            slideImages[index].classList.add('active');
        }
    }

    function startSlider() {
        if (slideImages.length > 0) {
            showSlide(currentSlide); // Show the first slide immediately
            setInterval(() => {
                currentSlide = (currentSlide + 1) % slideImages.length;
                showSlide(currentSlide);
            }, slideIntervalTime);
        }
    }

    startSlider(); // Start the slider when DOM is ready

    // Admin form specific logic (e.g., image/video upload via Cloudinary)
    // This is where you would add JavaScript for actual file uploads.
    // Example (highly simplified, requires more robust error handling and UI feedback):
    /*
    const uploadImageInput = document.getElementById('upload_image'); // Assuming an input with this ID for image upload
    if (uploadImageInput) {
        uploadImageInput.addEventListener('change', async (event) => {
            const file = event.target.files[0];
            if (!file) return;

            const formData = new FormData();
            formData.append('file', file);
            formData.append('upload_preset', 'YOUR_CLOUDINARY_UPLOAD_PRESET'); // Set this in Cloudinary

            try {
                // Replace YOUR_CLOUD_NAME with your actual Cloudinary cloud name
                const response = await fetch('https://api.cloudinary.com/v1_1/YOUR_CLOUD_NAME/image/upload', {
                    method: 'POST',
                    body: formData
                });
                const data = await response.json();
                if (data.secure_url) {
                    const imageUrlsTextarea = document.getElementById('images'); // Assuming a textarea with ID 'images'
                    imageUrlsTextarea.value += (imageUrlsTextarea.value ? '\n' : '') + data.secure_url;
                    alert('Image uploaded successfully!');
                } else {
                    alert('Image upload failed: ' + (data.error ? data.error.message : 'Unknown error'));
                }
            } catch (error) {
                console.error('Upload error:', error);
                alert('An error occurred during upload.');
            }
        });
    }

    const uploadVideoInput = document.getElementById('upload_video'); // Assuming an input with this ID for video upload
    if (uploadVideoInput) {
        uploadVideoInput.addEventListener('change', async (event) => {
            const file = event.target.files[0];
            if (!file) return;

            const formData = new FormData();
            formData.append('file', file);
            formData.append('upload_preset', 'YOUR_CLOUDINARY_UPLOAD_PRESET'); // Set this in Cloudinary

            try {
                // Replace YOUR_CLOUD_NAME with your actual Cloudinary cloud name
                const response = await fetch('https://api.cloudinary.com/v1_1/YOUR_CLOUD_NAME/video/upload', {
                    method: 'POST',
                    body: formData
                });
                const data = await response.json();
                if (data.secure_url) {
                    const videoUrlInput = document.getElementById('video_url'); // Assuming an input with ID 'video_url'
                    videoUrlInput.value = data.secure_url;
                    alert('Video uploaded successfully!');
                } else {
                    alert('Video upload failed: ' + (data.error ? data.error.error.message : 'Unknown error'));
                }
            } catch (error) {
                console.error('Upload error:', error);
                alert('An error occurred during upload.');
            }
        });
    }
    */
});
