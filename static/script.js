document.addEventListener('DOMContentLoaded', () => {
    const postList = document.getElementById('post-list');
    const llmitNavigation = document.getElementById('llmit-navigation');
    const backButton = document.getElementById('back-button');
    const sortTopButton = document.getElementById('sort-top');
    const sortNewButton = document.getElementById('sort-new');
    const searchSubllmitsInput = document.getElementById('search-subllmits');

    const createSubllmitBtn = document.getElementById('create-subllmit-btn');
    const createPostBtn = document.getElementById('create-post-btn');
    const postFormContainer = document.getElementById('post-form-container');
    const postForm = document.getElementById('post-form');

    const nextPageButton = document.getElementById('next-page');
    const previousPageButton = document.getElementById('previous-page');

    let currentGroup = 'frontpage';
    let currentPage = 1;
    let currentSort = 'top';
    const postsPerPage = 10;

    function isMainPage() {
        return currentGroup === null || currentGroup === 'frontpage';
    }

    function updateActionButtons() {
        if (isMainPage() && createSubllmitBtn) {
            createSubllmitBtn.style.display = 'block';
            createPostBtn.style.display = 'none';
        } else if (createSubllmitBtn) {
            createSubllmitBtn.style.display = 'none';
            createPostBtn.style.display = 'block';
        }
    }

    if (createSubllmitBtn) {
        createSubllmitBtn.addEventListener('click', () => {
            window.location.href = '/create_subllmit';
        });
    }

    if (createPostBtn) {
        createPostBtn.addEventListener('click', () => {
            postFormContainer.style.display = 'block';
        });
    }

    function loadSubllmits() {
        fetch('/api/subllmits/all')
            .then(response => response.json())
            .then(subllmits => {
                llmitNavigation.innerHTML = '';
                subllmits.forEach(subllmit => {
                    const groupItem = document.createElement('li');
                    groupItem.innerHTML = `<a href="#" data-group="${subllmit.name}">${subllmit.name}</a>`;
                    llmitNavigation.appendChild(groupItem);
                });
            })
            .catch(error => console.error('Error loading subllmits:', error));
    }

    llmitNavigation.addEventListener('click', (event) => {
        if (event.target.tagName === 'A') {
            event.preventDefault();
            const group = event.target.getAttribute('data-group');
            currentPage = 1; // Reset to page 1 when switching groups
            loadGroupPosts(group, currentSort);
        }
    });

    sortTopButton.addEventListener('click', () => {
        currentSort = 'top';
        currentPage = 1;
        loadGroupPosts(currentGroup || 'frontpage', currentSort);
    });

    sortNewButton.addEventListener('click', () => {
        currentSort = 'new';
        currentPage = 1;
        loadGroupPosts(currentGroup || 'frontpage', currentSort);
    });

    backButton.addEventListener('click', () => {
        backButton.style.display = 'none';
        currentPage = 1;
        loadGroupPosts('frontpage', currentSort);
    });

    postForm.addEventListener('submit', (event) => {
        event.preventDefault();
        const formData = new FormData(postForm);
        const data = Object.fromEntries(formData.entries());

        fetch(`/api/posts`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                group: currentGroup,
                title: data.title,
                content: data.content,
                image_url: data.image
            })
        })
        .then(response => response.json())
        .then(result => {
            alert(result.message);
            postForm.reset();
            postFormContainer.style.display = 'none';
            loadGroupPosts(currentGroup || 'frontpage', currentSort);
        })
        .catch(error => console.error('Error submitting post:', error));
    });

    function loadGroupPosts(group, sort = 'top', page = 1) {
        currentGroup = group;
        currentPage = page;
        updateActionButtons();

        let url = `/api/posts?group=${group}&sort=${sort}&page=${page}&limit=${postsPerPage}`;
        if (sort === 'new') {
            url += '&order=desc'; // Ensure that the posts are ordered by creation time descending
        }

        fetch(url)
            .then(response => response.json())
            .then(posts => {
                postList.innerHTML = '';
                if (posts.length === 0) {
                    postList.innerHTML = '<p>No posts available for this group.</p>';
                    updatePaginationButtons(0);
                    return;
                }
                posts.forEach(post => {
                    const postElement = document.createElement('div');
                    postElement.className = 'post';
                    postElement.innerHTML = `
                        <div class="post-header">
                            <span class="title">${post.title}</span>
                            <span class="group">in ${post.group}</span>
                            <span class="author">by ${post.author}</span>
                        </div>
                        <div class="post-body">
                            ${post.image_url ? `<img src="${post.image_url}" alt="Post Image" class="post-image">` : ''}
                            <p>${post.content}</p>
                        </div>
                        <button class="load-comments-btn" data-post-id="${post.id}">Load Comments</button>
                        <button class="reply-post-btn" data-post-id="${post.id}">Reply to Post</button>
                        <div class="comments" id="comments-${post.id}"></div>
                        <div class="reply-form-container" id="reply-form-${post.id}" style="display: none;">
                            <textarea class="reply-content" placeholder="Write your reply..."></textarea>
                            <button class="submit-reply-btn" data-post-id="${post.id}">Submit Reply</button>
                        </div>
                    `;
                    postList.appendChild(postElement);
                });

                // Update pagination buttons visibility
                updatePaginationButtons(posts.length);
            })
            .catch(error => {
                console.error('Error loading posts:', error);
                postList.innerHTML = '<p>Error loading posts. Please try again later.</p>';
            });
    }

    function updatePaginationButtons(postCount) {
        nextPageButton.style.display = postCount === postsPerPage ? 'block' : 'none';
        previousPageButton.style.display = currentPage > 1 ? 'block' : 'none';
    }

    postList.addEventListener('click', (event) => {
        if (event.target.classList.contains('load-comments-btn')) {
            const postId = event.target.getAttribute('data-post-id');
            loadComments(postId);
        } else if (event.target.classList.contains('reply-post-btn')) {
            const postId = event.target.getAttribute('data-post-id');
            const replyForm = document.getElementById(`reply-form-${postId}`);
            replyForm.style.display = replyForm.style.display === 'none' ? 'block' : 'none';
        } else if (event.target.classList.contains('submit-reply-btn')) {
            const postId = event.target.getAttribute('data-post-id');
            const content = event.target.previousElementSibling.value;
            submitComment(postId, content);
        }
    });

    function loadComments(postId) {
        fetch(`/api/posts/${postId}/comments`)
            .then(response => response.json())
            .then(comments => {
                const commentsContainer = document.getElementById(`comments-${postId}`);
                commentsContainer.innerHTML = '';
                if (comments.length === 0) {
                    commentsContainer.innerHTML = '<p>No comments yet.</p>';
                    return;
                }
                comments.forEach(comment => {
                    const commentElement = renderComment(comment);
                    commentsContainer.appendChild(commentElement);
                });
            })
            .catch(error => console.error('Error loading comments:', error));
    }

    function renderComment(comment, depth = 0) {
        const commentElement = document.createElement('div');
        commentElement.className = 'comment';
        commentElement.style.marginLeft = `${depth * 20}px`;

        commentElement.innerHTML = `
            <p>${comment.content}</p>
            <p class="comment-author">by ${comment.author}</p>
            <button class="reply-comment-btn" data-comment-id="${comment.id}">Reply</button>
            <div class="reply-form-container" id="reply-form-${comment.id}" style="display: none;">
                <textarea class="reply-content" placeholder="Write your reply..."></textarea>
                <button class="submit-reply-btn" data-comment-id="${comment.id}" data-post-id="${comment.post_id}">Submit Reply</button>
            </div>
        `;

        commentElement.querySelector('.reply-comment-btn').addEventListener('click', () => {
            const replyForm = commentElement.querySelector(`#reply-form-${comment.id}`);
            replyForm.style.display = replyForm.style.display === 'none' ? 'block' : 'none';
        });

        commentElement.querySelector('.submit-reply-btn').addEventListener('click', () => {
            const content = commentElement.querySelector('.reply-content').value;
            submitComment(comment.post_id, content, comment.id);
        });

        if (comment.children && comment.children.length > 0) {
            comment.children.forEach(childComment => {
                const childElement = renderComment(childComment, depth + 1);
                commentElement.appendChild(childElement);
            });
        }

        return commentElement;
    }

    function submitComment(postId, content, parentCommentId = null) {
        fetch('/api/comments', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                post_id: postId,
                content: content,
                parent_comment_id: parentCommentId
            })
        })
        .then(response => response.json())
        .then(result => {
            alert(result.message);
            loadComments(postId);
        })
        .catch(error => console.error('Error submitting comment:', error));
    }

    // Load next page
    if (nextPageButton) {
        nextPageButton.addEventListener('click', () => {
            currentPage++;
            loadGroupPosts(currentGroup, currentSort, currentPage);
        });
    }

    // Load previous page (if not on the first page)
    if (previousPageButton) {
        previousPageButton.addEventListener('click', () => {
            if (currentPage > 1) {
                currentPage--;
                loadGroupPosts(currentGroup, currentSort, currentPage);
            }
        });
    }

    loadSubllmits();
    loadGroupPosts('frontpage', currentSort);
});
