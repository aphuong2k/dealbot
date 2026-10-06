import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService, PostItem } from '../../services/api.service';
import { NzTableModule } from 'ng-zorro-antd/table';
import { NzButtonModule } from 'ng-zorro-antd/button';
import { NzSelectModule } from 'ng-zorro-antd/select';
import { NzTagModule } from 'ng-zorro-antd/tag';
import { NzMessageService } from 'ng-zorro-antd/message';
import { NzSpinModule } from 'ng-zorro-antd/spin';
import { NzModalModule } from 'ng-zorro-antd/modal';

@Component({
  selector: 'app-posts',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    NzTableModule,
    NzButtonModule,
    NzSelectModule,
    NzTagModule,
    NzSpinModule,
    NzModalModule
  ],
  templateUrl: './posts.component.html',
  styleUrls: ['./posts.component.css']
})
export class PostsComponent implements OnInit {
  posts: PostItem[] = [];
  loading = false;
  planLoading = false;
  runDueLoading = false;

  selectedStatus = '';
  selectedAccount = '';

  selectedPostForPreview: PostItem | null = null;
  previewModalVisible = false;

  statusOptions = [
    { label: 'Tất cả trạng thái', value: '' },
    { label: 'Đang xếp hàng (Queued)', value: 'queued' },
    { label: 'Đã đăng (Done)', value: 'done' },
    { label: 'Chờ admin duyệt (Pending)', value: 'pending_approval' },
    { label: 'Thất bại (Failed)', value: 'failed' },
    { label: 'Bỏ qua (Skipped)', value: 'skipped' }
  ];

  accountOptions = [
    { label: 'Tất cả nick', value: '' },
    { label: 'nick_a', value: 'nick_a' },
    { label: 'nick_b', value: 'nick_b' }
  ];

  constructor(
    private api: ApiService,
    private msg: NzMessageService
  ) {}

  ngOnInit(): void {
    this.fetchPosts();
  }

  fetchPosts(): void {
    this.loading = true;
    this.api.getPosts(this.selectedStatus || undefined, this.selectedAccount || undefined).subscribe({
      next: (data) => {
        this.posts = data;
        this.loading = false;
      },
      error: () => {
        this.loading = false;
        this.msg.error('Không thể tải lịch trình bài đăng!');
      }
    });
  }

  triggerPlan(): void {
    this.planLoading = true;
    this.api.planPosts().subscribe({
      next: (res) => {
        this.planLoading = false;
        this.msg.success(res.message);
        this.fetchPosts();
      },
      error: () => {
        this.planLoading = false;
        this.msg.error('Lỗi khi lập lịch hôm nay!');
      }
    });
  }

  triggerRunDue(): void {
    this.runDueLoading = true;
    this.api.runDuePosts().subscribe({
      next: (res) => {
        this.runDueLoading = false;
        this.msg.success(res.message);
        setTimeout(() => this.fetchPosts(), 3000);
      },
      error: () => {
        this.runDueLoading = false;
        this.msg.error('Lỗi khi kích hoạt phiên đăng bài!');
      }
    });
  }

  viewPost(post: PostItem): void {
    this.selectedPostForPreview = post;
    this.previewModalVisible = true;
  }

  closePreview(): void {
    this.previewModalVisible = false;
    this.selectedPostForPreview = null;
  }
}
