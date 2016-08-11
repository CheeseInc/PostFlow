#!/usr/bin/env python
# -*- coding: utf-8 -*-

# import re
import itertools
import mistune

from jinja2.utils import Markup

from datetime import datetime
from werkzeug import cached_property
from sqlalchemy.ext.hybrid import hybrid_property

from ..extensions import db
from ..helpers.text import slugify
from ..setting.models import get_setting


def get_all_posts(status=None, page=1, limit=None):
    limit = limit if limit else int(get_setting('postsPerPage').value)
    query = Post.query
    if status:
        query = query.filter(Post.status == status)
    return query.order_by(Post.updated_at.desc()).paginate(page, limit)


def get_post(id_or_slug):
    return Post.query.filter(
        db.or_(Post.id == id_or_slug, Post.slug == id_or_slug)).first_or_404()


def get_next_post(id):
    return Post.query.order_by(Post.id.asc()).filter(Post.id > id).first()


def get_prev_post(id):
    return Post.query.order_by(Post.id.desc()).filter(Post.id < id).first()


def add_post_views(id, views=1):
    post = Post.query.get(id)
    if not post:
        return
    post.views = post.views + views
    db.session.add(post)
    db.session.commit()


post_tag = db.Table(
    'post_tag',
    db.Column('post_id', db.Integer(), index=True),
    db.Column('tag_id', db.Integer(), index=True))


class Post(db.Model):

    STATUS_DRAFT = 'draft'
    STATUS_PUBLIC = 'published'
    STATUS_REMOVED = 'removed'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255))
    _slug = db.Column('slug', db.String(255), unique=True)
    _markdown = db.Column('markdown', db.Text)
    content = db.Column(db.Text)
    excerpt = db.Column(db.Text)
    views = db.Column(db.Integer, default=0)
    status = db.Column(db.String(150), default=STATUS_DRAFT)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, index=True)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow)
    updated_by = db.Column(db.Integer, index=True)

    __mapper_args__ = {'order_by': id.desc()}

    tags = db.relationship(
        'Tag',
        secondary=post_tag,
        primaryjoin='Post.id == post_tag.c.post_id',
        secondaryjoin='post_tag.c.tag_id==Tag.id',
        foreign_keys='[post_tag.c.post_id, post_tag.c.tag_id]',
        backref='posts')

    author = db.relationship(
        'User',
        primaryjoin='Post.created_by == User.id',
        foreign_keys='Post.created_by',
        backref='posts')

    @hybrid_property
    def markdown(self):
        return self._markdown

    @markdown.setter
    def markdown(self, markdown):
        self._markdown = markdown
        self.content = mistune.markdown(self._markdown)

    def get_excerpt(self, length=100):
        # return re.sub(r'<.*?>', '', (self.excerpt or self.content))[:length]
        return Markup(self.excerpt or self.content).striptags()[:length]

    @hybrid_property
    def slug(self):
        return self._slug

    @slug.setter
    def slug(self, slug):
        slugify_slug = slugify(slug) if slug else slugify(self.title)
        if not self._slug:
            self._slug = slugify_slug
            for x in itertools.count(1):
                if not db.session.query(
                        db.exists().where(Post.slug == self._slug)).scalar():
                    break
                self._slug = "{}-{}".format(slugify_slug, x)
            return
        self._slug = slugify_slug
