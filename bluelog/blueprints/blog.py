# -*- coding: utf-8 -*-
"""
    :author: Grey Li (李辉)
    :url: http://greyli.com
    :copyright: © 2018 Grey Li <withlihui@gmail.com>
    :license: MIT, see LICENSE for more details.
"""
from flask import render_template, flash, redirect, url_for, request, current_app, Blueprint, abort, make_response
from flask_login import current_user

from bluelog.emails import send_new_comment_email, send_new_reply_email
from bluelog.extensions import db
from bluelog.forms import CommentForm, AdminCommentForm
from bluelog.models import Post, Category, Comment
from bluelog.utils import redirect_back

blog_bp = Blueprint('blog', __name__)


@blog_bp.route('/')
def index():
    page = request.args.get('page', 1, type=int)
    per_page = current_app.config['BLUELOG_POST_PER_PAGE']
    # 查询Post数据表，按时间倒序排序，分页查询默认第一页10个
    pagination = Post.query.order_by(Post.timestamp.desc()).paginate(page, per_page=per_page)
    # pagination.items的类型是<class 'bluelog.models.Post'>
    posts = pagination.items
    return render_template('blog/index.html', pagination=pagination, posts=posts)


@blog_bp.route('/about')
def about():
    return render_template('blog/about.html')


@blog_bp.route('/category/<int:category_id>')
def show_category(category_id):
    category = Category.query.get_or_404(category_id)
    page = request.args.get('page', 1, type=int)
    per_page = current_app.config['BLUELOG_POST_PER_PAGE']
    # print(category)
    pagination = Post.query.with_parent(category).order_by(Post.timestamp.desc()).paginate(page, per_page)
    posts = pagination.items
    return render_template('blog/category.html', category=category, pagination=pagination, posts=posts)


@blog_bp.route('/post/<int:post_id>', methods=['GET', 'POST'])
def show_post(post_id):
    post = Post.query.get_or_404(post_id)
    # 获取?page=xxx，默认为1
    page = request.args.get('page', 1, type=int)
    per_page = current_app.config['BLUELOG_COMMENT_PER_PAGE']
    pagination = Comment.query.with_parent(post).filter_by(reviewed=True).order_by(Comment.timestamp.asc()).paginate(
        page, per_page)
    comments = pagination.items

    #如果管理员账户登录，在每一篇文章的评论部分会隐藏掉name、email、site字段的输入，使用当前账户信息自动赋值
    if current_user.is_authenticated:   #判断是否已经登录，如果登录使用管理员表单进行渲染
        form = AdminCommentForm()
        form.author.data = current_user.name
        form.email.data = current_app.config['BLUELOG_EMAIL']
        form.site.data = url_for('.index')
        from_admin = True
        reviewed = True
    else:   #如果未登录使用普通表单进行渲染
        form = CommentForm()
        from_admin = False
        reviewed = False

    if form.validate_on_submit():
        author = form.author.data
        email = form.email.data
        site = form.site.data
        body = form.body.data
        comment = Comment(
            author=author, email=email, site=site, body=body,
            from_admin=from_admin, post=post, reviewed=reviewed)
        replied_id = request.args.get('reply')
        if replied_id:
            replied_comment = Comment.query.get_or_404(replied_id)
            comment.replied = replied_comment
            send_new_reply_email(replied_comment)
        db.session.add(comment)
        db.session.commit()
        if current_user.is_authenticated:  # send message based on authentication status
            flash('Comment published.', 'success')
        else:
            flash('Thanks, your comment will be published after reviewed.', 'info')
            send_new_comment_email(post)  # send notification email to admin
        return redirect(url_for('.show_post', post_id=post_id))
    return render_template('blog/post.html', post=post, pagination=pagination, form=form, comments=comments)


@blog_bp.route('/reply/comment/<int:comment_id>')
def reply_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    if not comment.post.can_comment:
        flash('Comment is disabled.', 'warning')
        return redirect(url_for('.show_post', post_id=comment.post.id))
    return redirect(
        url_for('.show_post', post_id=comment.post_id, reply=comment_id, author=comment.author) + '#comment-form')

# 改变页面颜色
@blog_bp.route('/change-theme/<theme_name>')
def change_theme(theme_name):
    print(request.full_path)
    # current_app.config都是在settings.py中定义
    if theme_name not in current_app.config['BLUELOG_THEMES'].keys():
        abort(404)
    #改变页面颜色后还是返回当前页面
    response = make_response(redirect_back())
    # max_age设置cookie存在时间，单位是秒，这里是30天
    response.set_cookie('theme', theme_name, max_age=30 * 24 * 60 * 60)
    return response
