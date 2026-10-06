import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';

export interface BotStats {
  deals: { total: number; new: number };
  groups: { total: number; active: number; candidate: number; cooling_down: number };
  posts_today: { total: number; done: number; queued: number; pending_approval: number; failed: number; skipped: number };
  accounts: Array<{
    name: string;
    status: string;
    paused_hours_left: number;
    posts_today: number;
    max_posts_day: number;
    last_warmup_at: number;
  }>;
  dry_run: boolean;
  top_deals: any[];
}

export interface DealItem {
  id: string;
  niche: string;
  title: string;
  price: number;
  orig_price: number;
  discount: number;
  commission: number;
  rating: number;
  sold: number;
  url: string;
  aff_url: string;
  image: string;
  image_path?: string;
  score: number;
  status: string;
  is_valid: number;
  created_at: number;
}

export interface GroupItem {
  url: string;
  name: string;
  niche: string;
  members: number;
  status: 'candidate' | 'joined' | 'approved' | 'banned' | 'cooling_down' | 'skip';
  allow_link: number;
  account: string;
  last_posted_at: number;
  fail_count: number;
  success_count: number;
  consecutive_fails: number;
  priority_score: number;
  kind: 'niche' | 'dealhunt';
}

export interface PostItem {
  id: number;
  deal_id: string;
  group_url: string;
  group_name?: string;
  account: string;
  caption: string;
  comment: string;
  image_path: string;
  kind: string;
  status: string;
  sub_id: string;
  comment_status: string;
  comment_retry_at: number;
  comment_retries: number;
  scheduled_at: number;
  posted_at: number;
  error?: string;
}

export interface CouponItem {
  id: string;
  merchant: string;
  title: string;
  code: string;
  detail: string;
  start_at: number;
  end_at: number;
  url: string;
  aff_url: string;
  used: number;
}

export interface EventItem {
  title: string;
  merchant: string;
  start: string;
  end: string;
  detail: string;
  link: string;
}

@Injectable({
  providedIn: 'root'
})
export class ApiService {
  private baseUrl = 'http://localhost:8000/api';

  constructor(private http: HttpClient) {}

  getStats(): Observable<BotStats> {
    return this.http.get<BotStats>(`${this.baseUrl}/stats`);
  }

  getDeals(niche?: string, status?: string, search?: string): Observable<DealItem[]> {
    let params = new HttpParams();
    if (niche) params = params.set('niche', niche);
    if (status) params = params.set('status', status);
    if (search) params = params.set('search', search);
    return this.http.get<DealItem[]>(`${this.baseUrl}/deals`, { params });
  }

  crawlDeals(): Observable<any> {
    return this.http.post(`${this.baseUrl}/deals/crawl`, {});
  }

  getGroups(status?: string, kind?: string, search?: string): Observable<GroupItem[]> {
    let params = new HttpParams();
    if (status) params = params.set('status', status);
    if (kind) params = params.set('kind', kind);
    if (search) params = params.set('search', search);
    return this.http.get<GroupItem[]>(`${this.baseUrl}/groups`, { params });
  }

  updateGroup(url: string, data: Partial<GroupItem>): Observable<any> {
    let params = new HttpParams().set('url', url);
    return this.http.put(`${this.baseUrl}/groups`, data, { params });
  }

  discoverGroups(): Observable<any> {
    return this.http.post(`${this.baseUrl}/groups/discover`, {});
  }

  getPosts(status?: string, account?: string): Observable<PostItem[]> {
    let params = new HttpParams();
    if (status) params = params.set('status', status);
    if (account) params = params.set('account', account);
    return this.http.get<PostItem[]>(`${this.baseUrl}/posts`, { params });
  }

  planPosts(): Observable<any> {
    return this.http.post(`${this.baseUrl}/posts/plan`, {});
  }

  runDuePosts(): Observable<any> {
    return this.http.post(`${this.baseUrl}/posts/run-due`, {});
  }

  getCoupons(): Observable<CouponItem[]> {
    return this.http.get<CouponItem[]>(`${this.baseUrl}/coupons`);
  }

  refreshCoupons(): Observable<any> {
    return this.http.post(`${this.baseUrl}/coupons/refresh`, {});
  }

  getEvents(): Observable<EventItem[]> {
    return this.http.get<EventItem[]>(`${this.baseUrl}/events`);
  }

  saveEvents(events: EventItem[]): Observable<any> {
    return this.http.post(`${this.baseUrl}/events`, events);
  }

  getConfig(): Observable<any> {
    return this.http.get<any>(`${this.baseUrl}/config`);
  }

  updateConfig(cfg: any): Observable<any> {
    return this.http.put<any>(`${this.baseUrl}/config`, cfg);
  }

  warmupAccounts(): Observable<any> {
    return this.http.post(`${this.baseUrl}/accounts/warmup`, {});
  }

  testTelegramNotify(): Observable<any> {
    return this.http.post(`${this.baseUrl}/telegram/test-notify`, {});
  }

  postDigestTelegram(): Observable<any> {
    return this.http.post(`${this.baseUrl}/telegram/post-digest`, {});
  }
}
